import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from chat import services
from chat.models import Membership, Message, Room
from core.models import Candidatura, Freelance

from .helpers import (
    PNG_BYTES,
    client_for,
    make_candidatura,
    make_empresa,
    make_freelancer,
    make_vaga,
)

CONTACT_URL = '/api/chat/rooms/contact/'
ROOMS_URL = '/api/chat/rooms/'


def messages_url(room_id):
    return f'{ROOMS_URL}{room_id}/messages/'


def open_room(user, candidatura):
    return client_for(user).post(CONTACT_URL, {'candidatura': candidatura.pk})


class ContactTests(APITestCase):
    """Conversar a partir de uma candidatura (a única forma de criar uma conversa)."""

    def setUp(self):
        self.ana = make_freelancer('ana@example.com', 'Ana')
        self.bia = make_empresa('bia@example.com', 'Bia Tech')
        self.vaga = make_vaga(self.bia, titulo='Desenvolvedora Vue', cidade='Joinville', uf='SC')
        self.candidatura = make_candidatura(self.ana, self.vaga)

    def test_requires_login(self):
        response = self.client.post(CONTACT_URL, {'candidatura': self.candidatura.pk})

        self.assertEqual(response.status_code, 401)

    def test_freelancer_opens_a_room_with_the_company(self):
        response = open_room(self.ana, self.candidatura)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Bia Tech')
        self.assertEqual(response.data['other']['id'], self.bia.pk)
        self.assertEqual(
            response.data['pending_vaga'],
            {
                'id': self.vaga.pk,
                'titulo': 'Desenvolvedora Vue',
                'status': 'publicada',
                'modalidade': 'Remoto',
                'cidade': 'Joinville',
                'uf': 'SC',
                'empresa': self.bia.pk,
            },
        )
        self.assertEqual(
            sorted(Membership.objects.values_list('user_id', flat=True)),
            sorted([self.ana.pk, self.bia.pk]),
        )

    def test_company_opens_a_room_with_the_freelancer(self):
        self.ana.profissao = 'Web Developer'
        self.ana.save()

        response = open_room(self.bia, self.candidatura)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Ana')
        self.assertEqual(response.data['other']['id'], self.ana.pk)
        self.assertEqual(response.data['other']['profissao'], 'Web Developer')
        self.assertNotIn('telefone', response.data['other'])
        self.assertEqual(response.data['pending_vaga']['titulo'], 'Desenvolvedora Vue')

    def test_same_pair_reuses_the_room(self):
        first = open_room(self.ana, self.candidatura)
        outra = make_candidatura(self.ana, make_vaga(self.bia, titulo='Designer'))
        second = open_room(self.ana, outra)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['id'], first.data['id'])
        self.assertEqual(second.data['pending_vaga']['titulo'], 'Designer')
        self.assertEqual(Room.objects.count(), 1)

    def test_pair_is_the_same_from_both_sides(self):
        first = open_room(self.ana, self.candidatura)
        second = open_room(self.bia, self.candidatura)

        self.assertEqual(second.data['id'], first.data['id'])
        self.assertEqual(Room.objects.count(), 1)

    def test_any_status_can_open_a_room(self):
        for status in (Candidatura.Status.APROVADA, Candidatura.Status.RECUSADA):
            self.candidatura.status = status
            self.candidatura.save()

            self.assertIn(open_room(self.ana, self.candidatura).status_code, {200, 201})

    def test_only_the_two_parties_can_open_it(self):
        carla = make_freelancer('carla@example.com', 'Carla')
        outra_empresa = make_empresa('outra@example.com', 'Outra')

        for user in (carla, outra_empresa):
            response = open_room(user, self.candidatura)

            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data['detail'], 'Candidatura não encontrada.')

        self.assertEqual(Room.objects.count(), 0)

    def test_missing_candidatura_is_404(self):
        response = client_for(self.ana).post(CONTACT_URL, {'candidatura': 99999})

        self.assertEqual(response.status_code, 404)

    def test_vaga_without_company_is_400(self):
        legada = Freelance.objects.create(titulo='Vaga legada', preco=0, tempo='Texto livre')
        candidatura = make_candidatura(self.ana, legada)

        response = open_room(self.ana, candidatura)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Room.objects.count(), 0)

    def test_cannot_contact_yourself(self):
        candidatura = make_candidatura(self.bia, self.vaga)

        response = open_room(self.bia, candidatura)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Room.objects.count(), 0)

    def test_invalid_payload_is_400(self):
        client = client_for(self.ana)

        self.assertEqual(client.post(CONTACT_URL, {'candidatura': 'abc'}).status_code, 400)
        self.assertEqual(client.post(CONTACT_URL, {'anuncio': self.candidatura.pk}).status_code, 400)

    def test_there_is_no_other_way_to_create_a_room(self):
        client = client_for(self.ana)

        self.assertEqual(client.post(ROOMS_URL, {'name': 'x'}).status_code, 405)
        self.assertEqual(client.post(f'{ROOMS_URL}?members={self.bia.pk}').status_code, 405)
        self.assertEqual(client.get('/api/chat/users/?search=bia').status_code, 404)
        self.assertEqual(Room.objects.count(), 0)

    def test_clear_context_discards_the_card(self):
        room_id = open_room(self.ana, self.candidatura).data['id']
        client = client_for(self.ana)

        self.assertEqual(client.delete(f'{ROOMS_URL}{room_id}/context/').status_code, 204)
        self.assertIsNone(client.get(f'{ROOMS_URL}{room_id}/').data['pending_vaga'])

        message = client.post(messages_url(room_id), {'body': 'oi'}, format='json')

        self.assertIsNone(message.data['vaga'])

    def test_clear_context_requires_membership(self):
        room_id = open_room(self.ana, self.candidatura).data['id']
        carla = make_freelancer('carla@example.com', 'Carla')

        response = client_for(carla).delete(f'{ROOMS_URL}{room_id}/context/')

        self.assertEqual(response.status_code, 404)


class RoomListTests(APITestCase):
    def setUp(self):
        self.ana = make_freelancer('ana@example.com', 'Ana')
        self.bia = make_empresa('bia@example.com', 'Bia Tech')
        self.vaga = make_vaga(self.bia, titulo='Backend Django')
        self.room_id = open_room(self.ana, make_candidatura(self.ana, self.vaga)).data['id']

    def results(self, user):
        return client_for(user).get(ROOMS_URL).data['results']

    def test_initiator_sees_the_room_before_any_message(self):
        rooms = self.results(self.ana)

        self.assertEqual([room['id'] for room in rooms], [self.room_id])
        self.assertIsNotNone(rooms[0]['pending_vaga'])
        self.assertIsNone(rooms[0]['last_message'])

    def test_other_party_only_sees_the_room_after_the_first_message(self):
        self.assertEqual(self.results(self.bia), [])

        client_for(self.ana).post(messages_url(self.room_id), {'body': 'Oi, Bia!'}, format='json')
        rooms = self.results(self.bia)

        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]['name'], 'Ana')
        self.assertEqual(rooms[0]['unread'], 1)
        self.assertEqual(rooms[0]['last_message']['body'], 'Oi, Bia!')
        self.assertEqual(rooms[0]['last_message']['vaga']['titulo'], 'Backend Django')

    def test_vaga_is_the_pending_card_before_any_message(self):
        rooms = self.results(self.ana)

        assert rooms[0]['vaga']['titulo'] == 'Backend Django'
        assert rooms[0]['vaga'] == rooms[0]['pending_vaga']

    def test_vaga_is_the_last_card_sent_for_both_sides(self):
        client = client_for(self.ana)
        client.post(messages_url(self.room_id), {'body': 'Oi!'}, format='json')
        client.post(messages_url(self.room_id), {'body': 'sem cartão'}, format='json')

        for user in (self.ana, self.bia):
            rooms = self.results(user)

            assert rooms[0]['pending_vaga'] is None
            assert rooms[0]['last_message']['vaga'] is None
            assert rooms[0]['vaga']['titulo'] == 'Backend Django'
            assert rooms[0]['vaga']['id'] == self.vaga.pk

    def test_vaga_follows_the_newest_card(self):
        client = client_for(self.ana)
        client.post(messages_url(self.room_id), {'body': 'Oi!'}, format='json')
        open_room(self.ana, make_candidatura(self.ana, make_vaga(self.bia, titulo='Frontend Vue')))
        client.post(messages_url(self.room_id), {'body': 'E esta outra?'}, format='json')

        assert self.results(self.bia)[0]['vaga']['titulo'] == 'Frontend Vue'

    def test_last_card_wins_over_a_new_pending_one(self):
        client = client_for(self.ana)
        client.post(messages_url(self.room_id), {'body': 'Oi!'}, format='json')
        open_room(self.ana, make_candidatura(self.ana, make_vaga(self.bia, titulo='Frontend Vue')))

        room = self.results(self.ana)[0]

        assert room['pending_vaga']['titulo'] == 'Frontend Vue'
        assert room['vaga']['titulo'] == 'Backend Django'

    def test_deleted_card_is_ignored(self):
        client = client_for(self.ana)
        message_id = client.post(messages_url(self.room_id), {'body': 'Oi!'}, format='json').data['id']
        services.delete_message(self.ana, Room.objects.get(pk=self.room_id), message_id)
        client.post(messages_url(self.room_id), {'body': 'de novo'}, format='json')

        assert self.results(self.ana)[0]['vaga'] is None

    def test_vaga_is_none_without_any_card(self):
        client_for(self.ana).delete(f'{ROOMS_URL}{self.room_id}/context/')
        client_for(self.ana).post(messages_url(self.room_id), {'body': 'Oi!'}, format='json')

        assert self.results(self.bia)[0]['vaga'] is None

    def test_rooms_are_ordered_by_latest_message(self):
        carla = make_empresa('carla@example.com', 'Carla SA')
        second_id = open_room(self.ana, make_candidatura(self.ana, make_vaga(carla))).data['id']
        client = client_for(self.ana)

        client.post(messages_url(self.room_id), {'body': 'primeira'}, format='json')
        client.post(messages_url(second_id), {'body': 'segunda'}, format='json')

        self.assertEqual([room['id'] for room in self.results(self.ana)], [second_id, self.room_id])

    def test_other_people_never_see_the_room(self):
        carla = make_freelancer('carla@example.com', 'Carla')
        client_for(self.ana).post(messages_url(self.room_id), {'body': 'segredo'}, format='json')
        client = client_for(carla)

        self.assertEqual(self.results(carla), [])
        self.assertEqual(client.get(f'{ROOMS_URL}{self.room_id}/').status_code, 404)
        self.assertEqual(client.get(messages_url(self.room_id)).status_code, 404)
        self.assertEqual(client.post(messages_url(self.room_id), {'body': 'intruso'}, format='json').status_code, 404)
        self.assertEqual(client.post(f'{ROOMS_URL}{self.room_id}/read/').status_code, 404)

    def test_response_never_exposes_the_email(self):
        client_for(self.ana).post(messages_url(self.room_id), {'body': 'oi'}, format='json')

        self.assertNotIn('@', str(self.results(self.bia)))

    def test_requires_login(self):
        self.assertEqual(self.client.get(ROOMS_URL).status_code, 401)


class MessageTests(APITestCase):
    def setUp(self):
        self.ana = make_freelancer('ana@example.com', 'Ana')
        self.bia = make_empresa('bia@example.com', 'Bia Tech')
        self.vaga = make_vaga(self.bia, titulo='Analista de Dados')
        self.room_id = open_room(self.ana, make_candidatura(self.ana, self.vaga)).data['id']
        self.ana_client = client_for(self.ana)
        self.bia_client = client_for(self.bia)

    def send(self, client, body, **extra):
        return client.post(messages_url(self.room_id), {'body': body, **extra}, format='json')

    def test_card_goes_only_with_the_first_message(self):
        first = self.send(self.ana_client, 'Oi!')
        second = self.send(self.ana_client, 'Ainda tem?')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data['vaga']['titulo'], 'Analista de Dados')
        self.assertEqual(first.data['vaga']['id'], self.vaga.pk)
        self.assertIsNone(second.data['vaga'])
        self.assertIsNone(self.ana_client.get(f'{ROOMS_URL}{self.room_id}/').data['pending_vaga'])

    def test_the_other_person_does_not_get_a_card_from_a_reply(self):
        self.send(self.ana_client, 'Oi!')
        reply = self.send(self.bia_client, 'Olá, Ana!')

        self.assertIsNone(reply.data['vaga'])

    def test_card_survives_when_the_vaga_is_removed(self):
        self.send(self.ana_client, 'Oi!')
        self.vaga.delete()

        history = self.bia_client.get(messages_url(self.room_id)).data['results']

        self.assertEqual(history[0]['vaga']['titulo'], 'Analista de Dados')

    def test_pending_card_is_dropped_if_the_vaga_was_removed(self):
        self.vaga.delete()

        message = self.send(self.ana_client, 'Oi!')

        self.assertEqual(message.status_code, 201)
        self.assertIsNone(message.data['vaga'])

    def test_validation(self):
        self.assertEqual(self.send(self.ana_client, '   ').status_code, 400)
        self.assertEqual(self.send(self.ana_client, 'x' * 2001).status_code, 400)
        self.assertEqual(self.send(self.ana_client, 'ok', reply_to=99999).status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_reply_to_a_message_of_another_conversation_is_rejected(self):
        carla = make_empresa('carla@example.com', 'Carla SA')
        outro_room = open_room(self.ana, make_candidatura(self.ana, make_vaga(carla))).data['id']
        original = (
            client_for(self.ana).post(messages_url(outro_room), {'body': 'em outra conversa'}, format='json').data['id']
        )

        self.assertEqual(self.send(self.ana_client, 'oi', reply_to=original).status_code, 400)

    def test_reply_is_serialized_with_a_preview(self):
        original = self.send(self.ana_client, 'Posso começar segunda?').data['id']
        reply = self.send(self.bia_client, 'Quero!', reply_to=original)

        self.assertEqual(reply.data['reply_to']['id'], original)
        self.assertEqual(reply.data['reply_to']['body'], 'Posso começar segunda?')
        self.assertEqual(reply.data['reply_to']['author']['name'], 'Ana')

    def test_history_is_paginated_in_chronological_order(self):
        for number in range(services.PAGE_SIZE + 5):
            self.send(self.ana_client, f'mensagem {number}')

        latest = self.bia_client.get(messages_url(self.room_id)).data

        self.assertEqual(len(latest['results']), services.PAGE_SIZE)
        self.assertTrue(latest['has_more'])
        self.assertEqual(latest['results'][-1]['body'], f'mensagem {services.PAGE_SIZE + 4}')

        older = self.bia_client.get(messages_url(self.room_id), {'before': latest['next_before']}).data

        self.assertEqual(len(older['results']), 5)
        self.assertFalse(older['has_more'])
        self.assertEqual(older['results'][0]['body'], 'mensagem 0')

    def test_history_rejects_a_bad_cursor(self):
        self.assertEqual(self.ana_client.get(messages_url(self.room_id), {'before': 'x'}).status_code, 400)

    def test_unread_counter_and_read_receipt(self):
        first = self.send(self.ana_client, 'um').data
        self.send(self.ana_client, 'dois')
        rooms = self.bia_client.get(ROOMS_URL).data['results']

        self.assertEqual(rooms[0]['unread'], 2)
        self.assertFalse(first['read'])

        self.assertEqual(self.bia_client.post(f'{ROOMS_URL}{self.room_id}/read/').status_code, 204)

        rooms = self.bia_client.get(ROOMS_URL).data['results']
        history = self.ana_client.get(messages_url(self.room_id)).data['results']

        self.assertEqual(rooms[0]['unread'], 0)
        self.assertTrue(all(message['read'] for message in history))

    def test_own_messages_are_never_unread(self):
        self.send(self.ana_client, 'um')

        self.assertEqual(self.ana_client.get(ROOMS_URL).data['results'][0]['unread'], 0)

    def test_edit_and_delete_only_by_the_author(self):
        room = Room.objects.get(pk=self.room_id)
        message = services.send_message(self.ana, room, body='original')

        with self.assertRaises(Exception) as denied:
            services.edit_message(self.bia, room, message.pk, 'invasão')

        self.assertEqual(type(denied.exception).__name__, 'PermissionDenied')

        edited = services.edit_message(self.ana, room, message.pk, 'corrigida')

        self.assertEqual(edited.body, 'corrigida')
        self.assertIsNotNone(edited.edited_at)

        with self.assertRaises(Exception) as denied:
            services.delete_message(self.bia, room, message.pk)

        self.assertEqual(type(denied.exception).__name__, 'PermissionDenied')

        deleted = services.delete_message(self.ana, room, message.pk)

        self.assertTrue(deleted.is_deleted)
        self.assertIsNone(deleted.body)
        self.assertIsNone(deleted.vaga_card)

    def test_deleted_message_is_serialized_without_content(self):
        room = Room.objects.get(pk=self.room_id)
        message = services.send_message(self.ana, room, body='apagar')
        services.delete_message(self.ana, room, message.pk)

        data = self.bia_client.get(messages_url(self.room_id)).data['results'][0]

        self.assertTrue(data['is_deleted'])
        self.assertIsNone(data['body'])
        self.assertIsNone(data['vaga'])

    def test_cannot_edit_a_deleted_message(self):
        room = Room.objects.get(pk=self.room_id)
        message = services.send_message(self.ana, room, body='x')
        services.delete_message(self.ana, room, message.pk)

        with self.assertRaises(Exception) as error:
            services.edit_message(self.ana, room, message.pk, 'voltei')

        self.assertEqual(type(error.exception).__name__, 'ValidationError')


class AttachmentTests(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self.media, CHAT_MAX_UPLOAD_MB=1)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

        self.ana = make_freelancer('ana@example.com', 'Ana')
        self.bia = make_empresa('bia@example.com', 'Bia Tech')
        self.room_id = open_room(self.ana, make_candidatura(self.ana, make_vaga(self.bia))).data['id']
        self.ana_client = client_for(self.ana)
        self.bia_client = client_for(self.bia)

    def upload(self, name, content, content_type='application/octet-stream'):
        return self.ana_client.post(
            messages_url(self.room_id), {'file': SimpleUploadedFile(name, content, content_type)}, format='multipart'
        )

    def test_image_is_detected_by_content_and_served_inline(self):
        response = self.upload('foto.txt', PNG_BYTES, 'text/plain')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['file']['is_image'])
        self.assertEqual(response.data['file']['content_type'], 'image/png')
        self.assertEqual(response.data['file']['name'], 'foto.txt')

        download = self.bia_client.get(f'/api/chat/messages/{response.data["id"]}/file/')

        self.assertEqual(download.status_code, 200)
        self.assertEqual(download['Content-Type'], 'image/png')
        self.assertTrue(download['Content-Disposition'].startswith('inline'))
        self.assertEqual(download['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(b''.join(download.streaming_content), PNG_BYTES)

    def test_other_files_are_forced_to_download(self):
        response = self.upload('nota.html', b'<script>alert(1)</script>', 'text/html')
        download = self.bia_client.get(f'/api/chat/messages/{response.data["id"]}/file/')

        self.assertFalse(response.data['file']['is_image'])
        self.assertEqual(download['Content-Type'], 'application/octet-stream')
        self.assertTrue(download['Content-Disposition'].startswith('attachment'))

    def test_the_storage_path_is_never_exposed(self):
        response = self.upload('segredo.pdf', b'%PDF-1.4 conteudo')

        self.assertNotIn('chat_files', str(response.data))
        self.assertTrue(Message.objects.get(pk=response.data['id']).file.name.startswith('chat_files/'))

    def test_only_members_can_download(self):
        response = self.upload('a.pdf', b'%PDF-1.4 conteudo')
        carla = make_freelancer('carla@example.com', 'Carla')

        self.assertEqual(client_for(carla).get(f'/api/chat/messages/{response.data["id"]}/file/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/chat/messages/{response.data["id"]}/file/').status_code, 401)

    def test_size_limit_and_empty_file(self):
        self.assertEqual(self.upload('grande.bin', b'0' * (1024 * 1024 + 1)).status_code, 400)
        self.assertEqual(self.upload('vazio.bin', b'').status_code, 400)

    def test_text_and_file_together_are_rejected(self):
        response = self.ana_client.post(
            messages_url(self.room_id),
            {'body': 'oi', 'file': SimpleUploadedFile('a.pdf', b'%PDF-1.4 x')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)

    def test_deleting_the_message_removes_the_file(self):
        response = self.upload('a.pdf', b'%PDF-1.4 conteudo')
        message = Message.objects.get(pk=response.data['id'])
        path = message.file.path
        room = Room.objects.get(pk=self.room_id)

        services.delete_message(self.ana, room, message.pk)

        self.assertEqual(self.bia_client.get(f'/api/chat/messages/{message.pk}/file/').status_code, 404)

        with self.assertRaises(FileNotFoundError):
            open(path, 'rb')

"""Security regressions added after the original B54, covering the integrated chat."""

# ruff: noqa: PT009, PT027
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from channels.db import database_sync_to_async
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import re_path
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from chat import actions, services
from chat.models import Message, UserPresence
from chat.storage import AuthenticatedChatStorage
from chat.tests import test_consumer as ws
from chat.tests.helpers import FRONT_ORIGIN, make_candidatura, make_empresa, make_freelancer, make_vaga
from core.media import public_media


@override_settings(CORS_ALLOWED_ORIGINS=[FRONT_ORIGIN])
class LiveSocketSecurityTests(TransactionTestCase):
    def setUp(self):
        self.worker = make_freelancer('worker@b54.example.invalid')
        self.company = make_empresa('company@b54.example.invalid')
        job = make_vaga(self.company)
        self.room, _ = services.open_contact(self.worker, make_candidatura(self.worker, job).pk)

    async def expect_unauthorized(self, connection):
        output = await connection.receive_output(timeout=2)
        self.assertEqual(output['type'], 'websocket.close')
        self.assertEqual(output['code'], 4401)
        await connection.disconnect()

    @database_sync_to_async
    def change_password(self):
        self.worker.set_password('Replacement-B54-73829!')
        self.worker.save(update_fields=['password'])

    async def test_password_change_revokes_an_already_open_socket(self):
        connection = await ws.open_socket(self.worker)
        await self.change_password()
        await connection.send_json_to({'action': 'send', 'room': self.room.pk, 'body': 'must not persist'})
        await self.expect_unauthorized(connection)
        self.assertFalse(await database_sync_to_async(Message.objects.exists)())
        self.assertFalse(
            await database_sync_to_async(
                lambda: UserPresence.objects.filter(user=self.worker, connections__gt=0).exists()
            )()
        )

    async def test_deactivated_user_cannot_receive_broadcasts_on_an_open_socket(self):
        connection = await ws.open_socket(self.worker)
        await database_sync_to_async(type(self.worker).objects.filter(pk=self.worker.pk).update)(is_active=False)
        await database_sync_to_async(actions.send_message)(self.company, self.room, body='private update')
        await self.expect_unauthorized(connection)

    async def test_expired_token_cannot_receive_broadcasts_on_an_open_socket(self):
        token = AccessToken.for_user(self.worker)
        token.set_exp(lifetime=timedelta(seconds=60))
        connection = await ws.open_socket(token=str(token))
        with patch('rest_framework_simplejwt.tokens.aware_utcnow', return_value=timezone.now() + timedelta(minutes=2)):
            await database_sync_to_async(actions.send_message)(self.company, self.room, body='private update')
            await self.expect_unauthorized(connection)

    async def test_unknown_action_does_not_copy_arbitrary_input_to_logs(self):
        connection = await ws.open_socket(self.worker)
        marker = 'synthetic-private-marker'
        with self.assertLogs('chat', level='WARNING') as logs:
            await connection.send_json_to({'action': marker, 'room': self.room.pk})
            self.assertEqual((await connection.receive_json_from())['type'], 'error')
        self.assertNotIn(marker, str(logs.output))
        await connection.disconnect()

    async def test_malformed_action_and_reply_do_not_crash_socket(self):
        connection = await ws.open_socket(self.worker)
        try:
            for payload in [
                {'action': []},
                {'action': {}},
                {'action': 'send', 'room': self.room.pk, 'body': 'test', 'reply_to': []},
            ]:
                await connection.send_json_to(payload)
                self.assertEqual((await connection.receive_json_from())['type'], 'error')
        finally:
            await connection.disconnect()


class ChatMediaBoundaryTests(APITestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='.b54-media-', dir=Path(__file__).resolve().parents[2])
        self.addCleanup(directory.cleanup)
        root = directory.name

        class MediaUrls:
            urlpatterns = [re_path(r'^media/(?P<path>.*)$', public_media, {'document_root': root})]

        config = override_settings(MEDIA_ROOT=root, ROOT_URLCONF=MediaUrls)
        config.enable()
        self.addCleanup(config.disable)
        worker = make_freelancer('media-worker@b54.example.invalid')
        company = make_empresa('media-company@b54.example.invalid')
        room, _ = services.open_contact(worker, make_candidatura(worker, make_vaga(company)).pk)
        message = services.send_message(worker, room, file=SimpleUploadedFile('private.txt', b'private synthetic file'))
        self.file_name = message.file.name
        Path(root, 'users').mkdir()
        Path(root, 'users', 'public.png').write_bytes(b'public synthetic file')

    def test_anonymous_media_requests_cannot_bypass_chat_authorization(self):
        for path in [self.file_name, 'users/../' + self.file_name, self.file_name.replace('/', '\\')]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/media/' + path).status_code, 404)

    def test_existing_public_media_remains_available(self):
        response = self.client.get('/media/users/public.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'public synthetic file')


class CloudChatBoundaryTests(SimpleTestCase):
    def download(self, content=b'private synthetic file', status=200):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = status
        response.iter_content.return_value = iter([content])
        return response

    def test_new_chat_uploads_require_cloudinary_authenticated_delivery(self):
        with patch(
            'chat.storage.cloudinary.uploader.upload', return_value={'public_id': 'chat_files/synthetic'}
        ) as upload:
            AuthenticatedChatStorage()._upload('chat_files/synthetic.txt', b'synthetic')
        self.assertEqual(upload.call_args.kwargs['type'], 'authenticated')
        self.assertEqual(upload.call_args.kwargs['resource_type'], 'raw')

    def test_download_is_signed_inside_backend_and_url_cannot_be_serialized(self):
        response = self.download()
        storage = AuthenticatedChatStorage()
        with (
            patch(
                'chat.storage.cloudinary.utils.private_download_url',
                return_value='https://cloud.example.invalid/signed',
            ) as sign,
            patch('chat.storage.requests.get', return_value=response) as get,
        ):
            self.assertEqual(storage.open('chat_files/synthetic.txt').read(), b'private synthetic file')
        self.assertEqual(sign.call_args.kwargs['type'], 'authenticated')
        self.assertEqual(sign.call_args.kwargs['resource_type'], 'raw')
        get.assert_called_once_with(
            'https://cloud.example.invalid/signed', timeout=10, stream=True, allow_redirects=False
        )
        with self.assertRaises(ValueError):
            storage.url('chat_files/synthetic.txt')

    def test_old_chat_uploads_remain_readable_through_the_authorized_api(self):
        with (
            patch(
                'chat.storage.cloudinary.utils.private_download_url',
                return_value='https://cloud.example.invalid/signed',
            ) as sign,
            patch('chat.storage.requests.get', side_effect=[self.download(status=404), self.download()]),
        ):
            self.assertEqual(AuthenticatedChatStorage().open('chat_files/legacy.txt').read(), b'private synthetic file')
        self.assertEqual([call.kwargs['type'] for call in sign.call_args_list], ['authenticated', 'upload'])

    def test_redirects_and_excessive_downloads_are_rejected(self):
        with (
            patch(
                'chat.storage.cloudinary.utils.private_download_url',
                return_value='https://cloud.example.invalid/signed',
            ),
            patch('chat.storage.requests.get', return_value=self.download(status=302)) as get,
        ):
            with self.assertRaises(OSError):
                AuthenticatedChatStorage().open('chat_files/synthetic.txt')
            self.assertEqual(get.call_count, 1)
        with (
            override_settings(CHAT_MAX_UPLOAD_MB=1),
            patch(
                'chat.storage.cloudinary.utils.private_download_url',
                return_value='https://cloud.example.invalid/signed',
            ),
            patch('chat.storage.requests.get', return_value=self.download(b'x' * (1024 * 1024 + 1))),
        ):
            with self.assertRaises(OSError):
                AuthenticatedChatStorage().open('chat_files/synthetic.txt')

    def test_delete_invalidates_the_same_delivery_type_and_supports_legacy(self):
        with patch(
            'chat.storage.cloudinary.uploader.destroy', side_effect=[{'result': 'not found'}, {'result': 'ok'}]
        ) as destroy:
            self.assertTrue(AuthenticatedChatStorage().delete('chat_files/synthetic.txt'))
        self.assertEqual([call.kwargs['type'] for call in destroy.call_args_list], ['authenticated', 'upload'])
        self.assertTrue(all(call.kwargs['invalidate'] for call in destroy.call_args_list))

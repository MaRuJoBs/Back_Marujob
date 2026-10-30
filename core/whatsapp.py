"""Contato manual; nenhuma chamada de rede ou envio de mensagem é realizado."""

import re
from urllib.parse import urlencode

import phonenumbers

from core.models import Candidatura


def normalizar_telefone(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    # Reject extensions, prose, URLs and vanity numbers rather than guessing.
    if not re.fullmatch(r'\+?[0-9 ()\-.]+', value):
        return None
    digits = re.sub(r'[^0-9]', '', value)
    if value.startswith('+'):
        international = '+' + digits
    elif len(digits) in {10, 11} and not digits.startswith('0'):
        international = '+55' + digits
    elif len(digits) in {12, 13} and digits.startswith('55'):
        international = '+' + digits
    else:
        return None
    try:
        number = phonenumbers.parse(international, None)
    except phonenumbers.NumberParseException:
        return None
    if number.extension or not phonenumbers.is_valid_number(number):
        return None
    # No repaired/missing digits or silently removed trunk prefix.
    normalized = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    return normalized[1:] if normalized == international else None


def contato_whatsapp(candidatura):
    contact = {'disponivel': False, 'modo': 'link', 'url': None, 'mensagem_enviada': False}
    if candidatura.status != Candidatura.Status.APROVADA:
        return {**contact, 'motivo': 'candidatura_nao_aprovada'}
    phone = normalizar_telefone(candidatura.freelancer.telefone)
    if phone is None:
        return {**contact, 'motivo': 'telefone_invalido'}
    company = candidatura.oportunidade.empresa
    if company is None:
        return {**contact, 'motivo': 'empresa_indisponivel'}
    name = candidatura.freelancer.name or 'profissional'
    company_name = company.name or 'empresa'
    message = (
        f'Olá, {name}! Sua candidatura para a vaga {candidatura.oportunidade.titulo} '
        f'foi aprovada pela empresa {company_name} através do MaRuJoBs. '
        'Gostaríamos de conversar com você sobre os próximos passos.'
    )
    return {**contact, 'disponivel': True, 'url': f'https://wa.me/{phone}?{urlencode({"text": message})}'}

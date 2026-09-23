from django.db import models

from core.models.user import User


class Portfolio(models.Model):
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='portfolios',
    )
    imagem = models.ImageField(
        upload_to='portfolios/',
        null=True,
        blank=True,
    )

    titulo = models.CharField(max_length=255)
    categoria = models.CharField(max_length=100)
    descricao = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    link = models.URLField(blank=True)
    
    def __str__(self):
        return self.titulo
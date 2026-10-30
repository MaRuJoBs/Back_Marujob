from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from core.views import (
    CandidaturaViewSet,
    DefinirSenhaView,
    FavoritoViewSet,
    FreelanceViewSet,
    GoogleLoginView,
    NotificacaoViewSet,
    PortfolioViewSet,
    TrocarSenhaView,
    UserRegistrationView,
    UserViewSet,
)

router = DefaultRouter()

router.register(r'usuarios', UserViewSet, basename='usuarios')
router.register(r'freelances', FreelanceViewSet, basename='freelances')
router.register(r'portfolios', PortfolioViewSet, basename='portfolios')
router.register(r'favoritos', FavoritoViewSet, basename='favoritos')
router.register(r'candidaturas', CandidaturaViewSet, basename='candidaturas')
router.register(r'notificacoes', NotificacaoViewSet, basename='notificacoes')
urlpatterns = [
    path('admin/', admin.site.urls),
    # OpenAPI 3
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/doc/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
    # Autenticação JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/auth/definir-senha/', DefinirSenhaView.as_view(), name='definir_senha'),
    path('api/auth/trocar-senha/', TrocarSenhaView.as_view(), name='trocar_senha'),
    # Registro de usuários
    path('api/registro/', UserRegistrationView.as_view(), name='user_registration'),
    # API
    path('api/', include(router.urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

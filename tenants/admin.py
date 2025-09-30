from django.contrib import admin
from .models import Tenant, TenantSettings

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "subdomain", "created_at")
    search_fields = ("name", "subdomain")

@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "theme_color", "support_email", "nome_loja")
    search_fields = ("tenant__name", "support_email", "nome_loja")

    """def has_add_permission(self, request):
        # Bloqueia a adição se já houver qualquer TenantSettings
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)"""

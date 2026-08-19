from django.contrib import admin
from .models import Tenant, TenantSettings, HorarioFuncionamento

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

@admin.register(HorarioFuncionamento)
class HorarioFuncionamentoAdmin(admin.ModelAdmin):
    list_display = ("tenant", "get_dia_display", "horario_abre", "horario_fecha", "ativo", "data_especifica")
    list_filter = ("dia_semana", "ativo")
    search_fields = ("tenant__name", "descricao")
    ordering = ("tenant", "dia_semana", "horario_abre")
    
    def get_dia_display(self, obj):
        return obj.get_dia_semana_display()
    get_dia_display.short_description = "Dia da Semana"

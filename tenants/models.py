# tenants/models.py
from django.db import models

class Tenant(models.Model):
    name = models.CharField(max_length=100)
    subdomain = models.CharField(max_length=50, unique=True)
    whatsapp = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Additional model to store tenant-specific settings
class TenantSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='settings')
    theme_color = models.CharField(max_length=7, default='#FFFFFF')  # Hex color code
    logo_url = models.URLField(blank=True, null=True)
    support_email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"Settings for {self.tenant.name}"
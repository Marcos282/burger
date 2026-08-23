from datetime import datetime, timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from .utils import calcular_dias_restantes, normalizar_datetime


class ExpiracaoTests(SimpleTestCase):
	def test_calcula_dias_restantes_com_data_sem_timezone(self):
		agora = datetime(2026, 8, 23, 18, 0)
		data_expiracao = agora + timedelta(days=5)

		self.assertEqual(calcular_dias_restantes(data_expiracao, agora), 5)

	def test_preserva_data_com_timezone(self):
		valor = timezone.now()

		self.assertIs(normalizar_datetime(valor), valor)

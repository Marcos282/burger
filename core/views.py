from django.shortcuts import render, HttpResponse

from menu.models import Produto

def loja(request):

   print(">>> Tenant ativo:", request.tenant)     
   #return HttpResponse(f"Tenant atual: {request.tenant}")
   return render(request, 'loja/index.html')
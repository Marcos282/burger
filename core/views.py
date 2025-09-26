from django.shortcuts import render, HttpResponse, get_object_or_404

from menu.models import Produto, Category
from core.utils import formatar_brl 

def loja(request):

   categoria_id = request.GET.get("categoria_id")
   produtos = Produto.objects.none()

   if categoria_id is None:
 
      # Obtendo produtos do tenant atual
      produtos = Produto.objects.filter(
         tenant=request.tenant,
         category__exibir=True  # Filtra apenas categorias marcadas para exibir
      )
   else:
   
      # Se categoria_id for fornecido, filtra os produtos por essa categoria
      produtos = Produto.objects.filter(
         tenant=request.tenant,
         category__id=categoria_id  # Filtra apenas categorias marcadas para exibir
      )

   for produto in produtos:
      
       produto.preco_formatado = formatar_brl(produto.price)

   # Obtendo todas as categorias do tenant atual para exibir no menu categorias   
   categorias = Category.objects.filter(tenant=request.tenant)

   context = {
         'produtos': produtos,
         'categorias': categorias     
    }

   return render(request, 'loja/index.html', context=context)



def detalhe(request,produto_id):

   produto = get_object_or_404(Produto, tenant=request.tenant, id=produto_id)
   produto.price = formatar_brl(produto.price)

   # Obtendo todas as categorias do tenant atual para exibir no menu categorias   
   categorias = Category.objects.filter(tenant=request.tenant)
  
   context = {
      'produto' : produto,
      'categorias' : categorias
   }
   
   return render(request, 'loja/produto/detail.html', context)
from django.shortcuts import render

def loja(request):
    return render(request, 'loja/index.html')
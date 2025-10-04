from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, HttpResponse
from .forms import UserLoginForm, UserCreationForm

def login_view(request):
    form = UserLoginForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('painel')  
        else:
            error = 'Desculpe, parece que há alguns erros detectados, por favor tente novamente.'
    #return render(request, 'login/login.html', {'form': form, 'error': error})
    return render(request, 'login/demo1/dist/custom/pages/login/login-2.html', {'form': form, 'error': error})
    #return HttpResponse('Login page is under maintenance.')

def register_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('login')
    return render(request, 'register/register.html', {'form': form})

def painel_view(request):
    if request.user.is_authenticated:
        print('Sessão do usuário:', dict(request.session))
        user = request.user
        print('Dados do usuário:', dict(username=user.username, email=user.email, id=user.id))
        return render(request, 'painel/base.html')
    else:
        return redirect('login')

def logout_view(request):
    logout(request)
    return redirect('loja') 
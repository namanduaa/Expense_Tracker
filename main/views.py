from django.shortcuts import render


def index(request):
    context = {
        'title': 'My Django App',
        'message': 'Your project is ready for GitHub.',
    }
    return render(request, 'index.html', context)

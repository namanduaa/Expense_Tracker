from django.shortcuts import render


def index(request):
    context = {
        'title': 'My Django App',
        'message': 'Another update was added to this project.',
    }
    return render(request, 'index.html', context)

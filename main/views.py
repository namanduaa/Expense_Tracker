from django.shortcuts import render


def index(request):
    context = {
        'title': 'My Updated Django App',
        'message': 'This is a fresh change made in the project files.',
    }
    return render(request, 'index.html', context)

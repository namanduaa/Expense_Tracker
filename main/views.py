from django.http import HttpResponse
from django.shortcuts import render


def index(request):
    # Simple view demonstrating Django response
    return HttpResponse('Hello, Django!')

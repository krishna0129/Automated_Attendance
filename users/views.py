from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

from recognition.decorators import admin_required


@admin_required
def register(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Registered {user.username}. Now add their photos.")
        return redirect("add-photos")
    return render(request, "users/register.html", {"form": form})

import os

from django import forms

MAX_RESUME_MB = 2
ALLOWED_RESUME_TYPES = {".pdf", ".doc", ".docx"}


def validate_resume_file(f):
    """Shared by the apply form and the profile form."""
    if f:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_RESUME_TYPES:
            raise forms.ValidationError("Upload a PDF, DOC or DOCX file.")
        if f.size > MAX_RESUME_MB * 1024 * 1024:
            raise forms.ValidationError(f"File must be smaller than {MAX_RESUME_MB} MB.")
    return f


class ApplicationForm(forms.Form):
    resume = forms.FileField(
        required=False,
        label="Resume",
        widget=forms.FileInput(attrs={"accept": ".pdf,.doc,.docx"}),
        help_text="PDF, DOC or DOCX, up to 2 MB.",
    )

    def clean_resume(self):
        return validate_resume_file(self.cleaned_data.get("resume"))

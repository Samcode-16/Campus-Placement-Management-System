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


class CompanyForm(forms.ModelForm):
    class Meta:
        from .models import Company

        model = Company
        fields = (
            "name",
            "industry",
            "website",
            "contact_person",
            "contact_email",
            "contact_phone",
            "description",
        )
        labels = {
            "name": "Company Name",
            "industry": "Industry / Sector",
            "website": "Company Website",
            "contact_person": "Contact Person",
            "contact_email": "Contact Email",
            "contact_phone": "Contact Phone",
            "description": "Company Description",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Infosys, TCS, HDFC Bank"}),
            "industry": forms.TextInput(attrs={"placeholder": "e.g. Information Technology, Financial Services"}),
            "website": forms.URLInput(attrs={"placeholder": "https://www.example.com"}),
            "contact_person": forms.TextInput(attrs={"placeholder": "e.g. Talent Acquisition Lead"}),
            "contact_email": forms.EmailInput(attrs={"placeholder": "hr@example.com"}),
            "contact_phone": forms.TextInput(attrs={"placeholder": "e.g. +91 9845012345"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Overview of the company, domains, and operations..."}),
        }

    def clean_name(self):
        from .models import Company

        name = self.cleaned_data["name"].strip()
        qs = Company.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A company with this name is already registered.")
        return name


class PlacementDriveForm(forms.ModelForm):
    application_deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        label="Application Deadline",
    )
    drive_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        label="Drive Date & Time",
    )

    class Meta:
        from .models import PlacementDrive

        model = PlacementDrive
        fields = (
            "company",
            "title",
            "category",
            "job_description",
            "package_lpa",
            "minimum_cgpa",
            "maximum_backlogs",
            "eligible_departments",
            "application_deadline",
            "drive_date",
            "vacancies",
            "status",
        )
        labels = {
            "company": "Recruiting Partner Company",
            "title": "Drive Title / Job Role",
            "category": "Industry Sector / Category",
            "job_description": "Job Description & Responsibilities",
            "package_lpa": "Annual Package (₹ LPA)",
            "minimum_cgpa": "Minimum CGPA Cutoff (0.00 - 10.00)",
            "maximum_backlogs": "Maximum Allowed Active Backlogs",
            "eligible_departments": "Eligible Departments",
            "vacancies": "Open Vacancies",
            "status": "Drive Status",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Associate Software Engineer"}),
            "job_description": forms.Textarea(attrs={"rows": 5, "placeholder": "Detailed role requirements, skills, and expectations..."}),
            "package_lpa": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "e.g. 7.50"}),
            "minimum_cgpa": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "10", "placeholder": "e.g. 7.00"}),
            "maximum_backlogs": forms.NumberInput(attrs={"min": "0", "placeholder": "0"}),
            "vacancies": forms.NumberInput(attrs={"min": "1", "placeholder": "1"}),
        }

    def clean_minimum_cgpa(self):
        cgpa = self.cleaned_data["minimum_cgpa"]
        if cgpa < 0 or cgpa > 10:
            raise forms.ValidationError("Minimum CGPA cutoff must be between 0.00 and 10.00.")
        return cgpa

    def clean_maximum_backlogs(self):
        backlogs = self.cleaned_data["maximum_backlogs"]
        if backlogs < 0:
            raise forms.ValidationError("Maximum active backlogs cannot be negative.")
        return backlogs

    def clean_package_lpa(self):
        pkg = self.cleaned_data["package_lpa"]
        if pkg < 0:
            raise forms.ValidationError("Package cannot be negative.")
        return pkg

    def clean_vacancies(self):
        vacancies = self.cleaned_data["vacancies"]
        if vacancies < 1:
            raise forms.ValidationError("Vacancies must be at least 1.")
        return vacancies

    def clean(self):
        cleaned_data = super().clean()
        deadline = cleaned_data.get("application_deadline")
        drive_date = cleaned_data.get("drive_date")
        if deadline and drive_date and deadline > drive_date:
            raise forms.ValidationError("Application deadline cannot be scheduled after the drive date.")
        return cleaned_data



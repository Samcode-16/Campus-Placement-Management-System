from django import forms
from .models import TrainingProgram


class TrainingProgramForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        input_formats=["%Y-%m-%d"],
        label="Program Start Date",
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        input_formats=["%Y-%m-%d"],
        label="Program End Date",
    )

    class Meta:
        model = TrainingProgram
        fields = (
            "title",
            "trainer",
            "mode",
            "status",
            "start_date",
            "end_date",
            "capacity",
            "description",
        )
        labels = {
            "title": "Training Program Title",
            "trainer": "Trainer / Resource Person / Agency",
            "mode": "Delivery Mode",
            "status": "Program Status",
            "capacity": "Maximum Batch Capacity",
            "description": "Program Curriculum & Overview",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Full-Stack Web Development Bootcamp"}),
            "trainer": forms.TextInput(attrs={"placeholder": "e.g. Dr. Rajesh Rao / Industry Academy"}),
            "capacity": forms.NumberInput(attrs={"min": "1", "placeholder": "30"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Outline syllabus, learning objectives, schedule, and prerequisites..."}),
        }

    def clean_capacity(self):
        capacity = self.cleaned_data.get("capacity")
        if capacity is not None and capacity < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        return capacity

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Program start date cannot be scheduled after the end date.")
        return cleaned_data

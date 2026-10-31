import os

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from accounts.forms import AdminStudentEditForm
from accounts.models import Department, StudentProfile
from recruitment.forms import CompanyForm, PlacementDriveForm
from recruitment.models import Application, Company, PlacementDrive
from training.forms import TrainingProgramForm
from training.models import TrainingEnrollment, TrainingProgram


# =========================================================================
# A. STUDENT MANAGEMENT
# =========================================================================

@staff_required
def admin_student_list_view(request):
    """Lists registered students with search, department & year filters, and pagination."""
    students = (
        StudentProfile.objects.select_related("user", "department")
        .order_by("usn")
    )

    query = request.GET.get("q", "").strip()
    if query:
        students = students.filter(
            Q(usn__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
        )

    dept_id = request.GET.get("department", "").strip()
    if dept_id.isdigit():
        students = students.filter(department_id=int(dept_id))

    year = request.GET.get("year", "").strip()
    if year.isdigit():
        students = students.filter(graduation_year=int(year))

    status_filter = request.GET.get("status", "").strip()
    if status_filter == "active":
        students = students.filter(user__is_active=True)
    elif status_filter == "inactive":
        students = students.filter(user__is_active=False)

    paginator = Paginator(students, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Filter options
    departments = Department.objects.all()
    graduation_years = (
        StudentProfile.objects.values_list("graduation_year", flat=True)
        .distinct()
        .order_by("graduation_year")
    )

    # Preserve GET parameters (except page) for pagination links
    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    context = {
        "page_obj": page_obj,
        "departments": departments,
        "graduation_years": graduation_years,
        "selected_dept": int(dept_id) if dept_id.isdigit() else "",
        "selected_year": int(year) if year.isdigit() else "",
        "selected_status": status_filter,
        "search_query": query,
        "query_string": query_string,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/students/list.html", context)


@staff_required
def admin_student_detail_view(request, pk):
    """Displays the complete profile, consent records, applications, and training programs of a student."""
    student = get_object_or_404(
        StudentProfile.objects.select_related("user", "department"),
        pk=pk,
    )
    applications = (
        student.applications.select_related("drive__company", "offer")
        .prefetch_related("interview_rounds")
        .order_by("-applied_at")
    )
    training_enrollments = (
        student.training_enrollments.select_related("program").order_by(
            "-enrolled_at"
        )
    )

    context = {
        "student": student,
        "applications": applications,
        "training_enrollments": training_enrollments,
    }
    return render(request, "admin_portal/students/detail.html", context)


@staff_required
def admin_student_edit_view(request, pk):
    """Allows administrators to edit academic and contact information for a student.
    Student passwords are never exposed.
    """
    student = get_object_or_404(
        StudentProfile.objects.select_related("user", "department"),
        pk=pk,
    )

    form = AdminStudentEditForm(
        request.POST or None, request.FILES or None, instance=student
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            f"Student {student.usn} ({student.user.get_full_name() or student.user.username}) updated successfully.",
        )
        return redirect("admin_student_detail", pk=student.pk)

    context = {"student": student, "form": form}
    return render(request, "admin_portal/students/edit.html", context)


@staff_required
@require_POST
def admin_student_toggle_status_view(request, pk):
    """Activates or deactivates a student account."""
    student = get_object_or_404(
        StudentProfile.objects.select_related("user"), pk=pk
    )
    user = student.user
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    status_str = "activated" if user.is_active else "deactivated"
    if user.is_active:
        messages.success(
            request, f"Student account for {student.usn} has been activated."
        )
    else:
        messages.warning(
            request,
            f"Student account for {student.usn} has been deactivated. The student cannot log in.",
        )

    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("admin_student_detail", pk=student.pk)


@staff_required
def admin_student_resume_view(request, pk):
    """Secure, authorized view/download of student resume file."""
    student = get_object_or_404(StudentProfile, pk=pk)
    if not student.resume:
        messages.error(request, f"Student {student.usn} has not uploaded a resume.")
        return redirect("admin_student_detail", pk=student.pk)

    try:
        resume_file = student.resume.open("rb")
    except (FileNotFoundError, ValueError):
        messages.error(
            request, f"The resume file for {student.usn} could not be found on the server."
        )
        return redirect("admin_student_detail", pk=student.pk)

    filename = os.path.basename(student.resume.name)
    ext = os.path.splitext(filename)[1].lower()
    content_type = "application/pdf" if ext == ".pdf" else "application/octet-stream"

    return FileResponse(
        resume_file,
        content_type=content_type,
        as_attachment=False,
        filename=filename,
    )


# =========================================================================
# B. COMPANY MANAGEMENT
# =========================================================================

@staff_required
def admin_company_list_view(request):
    """Displays all companies with search and drive statistics in a paginated table."""
    companies = (
        Company.objects.annotate(drives_count=Count("drives"))
        .order_by("name")
    )

    query = request.GET.get("q", "").strip()
    if query:
        companies = companies.filter(
            Q(name__icontains=query) | Q(industry__icontains=query)
        )

    paginator = Paginator(companies, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    context = {
        "page_obj": page_obj,
        "search_query": query,
        "query_string": query_string,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/companies/list.html", context)


@staff_required
def admin_company_create_view(request):
    """Allows administrators to register a new partner company."""
    form = CompanyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        messages.success(
            request, f"Partner company '{company.name}' created successfully."
        )
        return redirect("admin_company_detail", pk=company.pk)

    context = {"form": form, "action_title": "Add Partner Company"}
    return render(request, "admin_portal/companies/form.html", context)


@staff_required
def admin_company_detail_view(request, pk):
    """Displays comprehensive company details and all associated placement drives."""
    company = get_object_or_404(
        Company.objects.annotate(drives_count=Count("drives")), pk=pk
    )
    drives = company.drives.annotate(
        applications_count=Count("applications")
    ).order_by("-drive_date")

    total_applications = Application.objects.filter(drive__company=company).count()
    total_selected = Application.objects.filter(
        drive__company=company, status=Application.Status.SELECTED
    ).count()

    context = {
        "company": company,
        "drives": drives,
        "total_applications": total_applications,
        "total_selected": total_selected,
    }
    return render(request, "admin_portal/companies/detail.html", context)


@staff_required
def admin_company_edit_view(request, pk):
    """Allows administrators to edit an existing company's profile."""
    company = get_object_or_404(Company, pk=pk)

    form = CompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        messages.success(
            request, f"Company '{company.name}' updated successfully."
        )
        return redirect("admin_company_detail", pk=company.pk)

    context = {
        "company": company,
        "form": form,
        "action_title": f"Edit Company: {company.name}",
    }
    return render(request, "admin_portal/companies/form.html", context)


@staff_required
@require_POST
def admin_company_delete_view(request, pk):
    """Safely deletes a company only after verifying foreign-key dependencies."""
    company = get_object_or_404(Company, pk=pk)

    drives_count = company.drives.count()
    if drives_count > 0:
        messages.error(
            request,
            f"Cannot delete company '{company.name}' because it has {drives_count} "
            f"associated placement drive(s). Remove or reassign these drives first.",
        )
        return redirect("admin_company_detail", pk=company.pk)

    company_name = company.name
    company.delete()
    messages.success(
        request, f"Partner company '{company_name}' has been safely deleted."
    )
    return redirect("admin_company_list")


# =========================================================================
# C. PLACEMENT DRIVE MANAGEMENT
# =========================================================================

@staff_required
def admin_drive_list_view(request):
    """Lists all placement drives with search, category/status/company filters, and pagination."""
    drives = (
        PlacementDrive.objects.select_related("company")
        .prefetch_related("eligible_departments")
        .annotate(applications_count=Count("applications"))
        .order_by("-drive_date")
    )

    query = request.GET.get("q", "").strip()
    if query:
        drives = drives.filter(
            Q(title__icontains=query) | Q(company__name__icontains=query)
        )

    category = request.GET.get("category", "").strip()
    if category in PlacementDrive.Category.values:
        drives = drives.filter(category=category)

    status_filter = request.GET.get("status", "").strip()
    if status_filter in PlacementDrive.Status.values:
        drives = drives.filter(status=status_filter)

    company_id = request.GET.get("company", "").strip()
    if company_id.isdigit():
        drives = drives.filter(company_id=int(company_id))

    paginator = Paginator(drives, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    companies = Company.objects.order_by("name")

    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    context = {
        "page_obj": page_obj,
        "companies": companies,
        "category_choices": PlacementDrive.Category.choices,
        "status_choices": PlacementDrive.Status.choices,
        "selected_category": category,
        "selected_status": status_filter,
        "selected_company": int(company_id) if company_id.isdigit() else "",
        "search_query": query,
        "query_string": query_string,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/drives/list.html", context)


@staff_required
def admin_drive_create_view(request):
    """Allows administrators to create a new placement drive."""
    form = PlacementDriveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        drive = form.save()
        messages.success(
            request,
            f"Placement drive '{drive.title}' for {drive.company.name} created successfully.",
        )
        return redirect("admin_drive_detail", pk=drive.pk)

    context = {"form": form, "action_title": "Create Placement Drive"}
    return render(request, "admin_portal/drives/form.html", context)


@staff_required
def admin_drive_detail_view(request, pk):
    """Displays comprehensive drive specifications and student application roster."""
    drive = get_object_or_404(
        PlacementDrive.objects.select_related("company").prefetch_related(
            "eligible_departments"
        ),
        pk=pk,
    )
    applications = (
        drive.applications.select_related(
            "student__user", "student__department", "offer"
        )
        .prefetch_related("interview_rounds")
        .order_by("-applied_at")
    )

    app_stats = {
        "total": applications.count(),
        "applied": applications.filter(status=Application.Status.APPLIED).count(),
        "shortlisted": applications.filter(status=Application.Status.SHORTLISTED).count(),
        "selected": applications.filter(status=Application.Status.SELECTED).count(),
        "rejected": applications.filter(status=Application.Status.REJECTED).count(),
        "withdrawn": applications.filter(status=Application.Status.WITHDRAWN).count(),
    }

    context = {
        "drive": drive,
        "applications": applications,
        "app_stats": app_stats,
        "status_choices": PlacementDrive.Status.choices,
        "reviewable_choices": [
            c for c in Application.Status.choices
            if c[0] != Application.Status.WITHDRAWN
        ],
    }
    return render(request, "admin_portal/drives/detail.html", context)


@staff_required
def admin_drive_edit_view(request, pk):
    """Allows administrators to modify an existing placement drive."""
    drive = get_object_or_404(PlacementDrive, pk=pk)
    form = PlacementDriveForm(request.POST or None, instance=drive)
    if request.method == "POST" and form.is_valid():
        drive = form.save()
        messages.success(
            request, f"Placement drive '{drive.title}' updated successfully."
        )
        return redirect("admin_drive_detail", pk=drive.pk)

    context = {
        "drive": drive,
        "form": form,
        "action_title": f"Edit Drive: {drive.title}",
    }
    return render(request, "admin_portal/drives/form.html", context)


@staff_required
@require_POST
def admin_drive_delete_view(request, pk):
    """Safely deletes a placement drive only if no applications exist."""
    drive = get_object_or_404(PlacementDrive, pk=pk)
    app_count = drive.applications.count()
    if app_count > 0:
        messages.error(
            request,
            f"Cannot delete placement drive '{drive.title}' because it has {app_count} "
            f"student application(s) linked to it. Applications must be removed or handled first.",
        )
        return redirect("admin_drive_detail", pk=drive.pk)

    drive_title = drive.title
    drive.delete()
    messages.success(
        request, f"Placement drive '{drive_title}' has been deleted successfully."
    )
    return redirect("admin_drive_list")


@staff_required
@require_POST
def admin_drive_status_view(request, pk):
    """Changes the status of a placement drive (DRAFT, OPEN, CLOSED, COMPLETED)."""
    drive = get_object_or_404(PlacementDrive, pk=pk)
    new_status = request.POST.get("status")
    if new_status in PlacementDrive.Status.values:
        drive.status = new_status
        drive.save(update_fields=["status"])
        messages.success(
            request, f"Drive status updated to '{drive.get_status_display()}'."
        )
    else:
        messages.error(request, "Invalid status choice selected.")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect("admin_drive_detail", pk=drive.pk)


# =========================================================================
# D. APPLICATION MANAGEMENT
# =========================================================================

@staff_required
def admin_application_list_view(request):
    """Displays all student applications with search, multi-faceted filtering, and pagination."""
    applications = (
        Application.objects.select_related(
            "student__user",
            "student__department",
            "drive__company",
            "offer",
        )
        .prefetch_related("interview_rounds")
        .order_by("-applied_at")
    )

    query = request.GET.get("q", "").strip()
    if query:
        applications = applications.filter(
            Q(student__usn__icontains=query)
            | Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
            | Q(student__user__username__icontains=query)
        )

    company_id = request.GET.get("company", "").strip()
    if company_id.isdigit():
        applications = applications.filter(drive__company_id=int(company_id))

    drive_id = request.GET.get("drive", "").strip()
    if drive_id.isdigit():
        applications = applications.filter(drive_id=int(drive_id))

    dept_id = request.GET.get("department", "").strip()
    if dept_id.isdigit():
        applications = applications.filter(student__department_id=int(dept_id))

    status_filter = request.GET.get("status", "").strip()
    if status_filter in Application.Status.values:
        applications = applications.filter(status=status_filter)

    paginator = Paginator(applications, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    companies = Company.objects.order_by("name")
    drives = PlacementDrive.objects.select_related("company").order_by("-drive_date")
    departments = Department.objects.all()

    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    context = {
        "page_obj": page_obj,
        "companies": companies,
        "drives": drives,
        "departments": departments,
        "status_choices": Application.Status.choices,
        "reviewable_choices": [
            c for c in Application.Status.choices
            if c[0] != Application.Status.WITHDRAWN
        ],
        "selected_company": int(company_id) if company_id.isdigit() else "",
        "selected_drive": int(drive_id) if drive_id.isdigit() else "",
        "selected_dept": int(dept_id) if dept_id.isdigit() else "",
        "selected_status": status_filter,
        "search_query": query,
        "query_string": query_string,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/applications/list.html", context)


@staff_required
def admin_application_detail_view(request, pk):
    """Displays comprehensive application profile, interview rounds, and offers."""
    application = get_object_or_404(
        Application.objects.select_related(
            "student__user",
            "student__department",
            "drive__company",
            "offer",
        ).prefetch_related("interview_rounds"),
        pk=pk,
    )

    context = {
        "application": application,
        "status_choices": Application.Status.choices,
        "reviewable_choices": [
            c for c in Application.Status.choices
            if c[0] != Application.Status.WITHDRAWN
        ],
    }
    return render(request, "admin_portal/applications/detail.html", context)


@staff_required
@require_POST
def admin_application_status_view(request, pk):
    """Updates an application status and confirms student visibility."""
    application = get_object_or_404(
        Application.objects.select_related("student__user", "drive"),
        pk=pk,
    )
    new_status = request.POST.get("status")

    if new_status in Application.Status.values:
        old_status_label = application.get_status_display()
        application.status = new_status
        application.save(update_fields=["status"])
        messages.success(
            request,
            f"Application for {application.student.usn} ({application.student.user.get_full_name() or application.student.user.username}) updated from '{old_status_label}' to '{application.get_status_display()}'.",
        )
    else:
        messages.error(request, "Invalid application status specified.")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect("admin_application_detail", pk=application.pk)


@staff_required
def admin_application_resume_view(request, pk):
    """Secure, authorized streaming of the application's uploaded resume file."""
    application = get_object_or_404(
        Application.objects.select_related("student"),
        pk=pk,
    )
    resume_file_field = application.resume or application.student.resume

    if not resume_file_field:
        messages.error(
            request,
            f"No resume document attached to application #{application.pk} for {application.student.usn}.",
        )
        return redirect("admin_application_detail", pk=application.pk)

    try:
        resume_file = resume_file_field.open("rb")
    except (FileNotFoundError, ValueError):
        messages.error(
            request,
            f"The resume file for {application.student.usn} could not be located on the server storage.",
        )
        return redirect("admin_application_detail", pk=application.pk)

    filename = os.path.basename(resume_file_field.name)
    ext = os.path.splitext(filename)[1].lower()
    content_type = "application/pdf" if ext == ".pdf" else "application/octet-stream"

    return FileResponse(
        resume_file,
        content_type=content_type,
        as_attachment=False,
        filename=filename,
    )


# =========================================================================
# E. TRAINING PROGRAM MANAGEMENT
# =========================================================================

@staff_required
def admin_training_list_view(request):
    """Lists all training programs with search, mode/status filters, and pagination."""
    programs = (
        TrainingProgram.objects.annotate(enrollments_count=Count("enrollments"))
        .order_by("-start_date")
    )

    query = request.GET.get("q", "").strip()
    if query:
        programs = programs.filter(
            Q(title__icontains=query)
            | Q(trainer__icontains=query)
            | Q(description__icontains=query)
        )

    mode = request.GET.get("mode", "").strip()
    if mode in TrainingProgram.Mode.values:
        programs = programs.filter(mode=mode)

    status_filter = request.GET.get("status", "").strip()
    if status_filter in TrainingProgram.Status.values:
        programs = programs.filter(status=status_filter)

    paginator = Paginator(programs, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    context = {
        "page_obj": page_obj,
        "mode_choices": TrainingProgram.Mode.choices,
        "status_choices": TrainingProgram.Status.choices,
        "selected_mode": mode,
        "selected_status": status_filter,
        "search_query": query,
        "query_string": query_string,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/training/list.html", context)


@staff_required
def admin_training_create_view(request):
    """Allows administrators to create a new training program."""
    form = TrainingProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        program = form.save()
        messages.success(
            request, f"Training program '{program.title}' created successfully."
        )
        return redirect("admin_training_detail", pk=program.pk)

    context = {"form": form, "action_title": "Add Training Program"}
    return render(request, "admin_portal/training/form.html", context)


@staff_required
def admin_training_detail_view(request, pk):
    """Displays comprehensive training program specifications and enrolled student roster."""
    program = get_object_or_404(
        TrainingProgram.objects.annotate(enrollments_count=Count("enrollments")),
        pk=pk,
    )
    enrollments = (
        program.enrollments.select_related("student__user", "student__department")
        .order_by("-enrolled_at")
    )

    stats = enrollments.aggregate(
        avg_attendance=Avg("attendance_percentage"),
        avg_score=Avg("assessment_score"),
    )

    status_counts = {
        "total": enrollments.count(),
        "enrolled": enrollments.filter(completion_status=TrainingEnrollment.CompletionStatus.ENROLLED).count(),
        "in_progress": enrollments.filter(completion_status=TrainingEnrollment.CompletionStatus.IN_PROGRESS).count(),
        "completed": enrollments.filter(completion_status=TrainingEnrollment.CompletionStatus.COMPLETED).count(),
        "dropped": enrollments.filter(completion_status=TrainingEnrollment.CompletionStatus.DROPPED).count(),
    }

    context = {
        "program": program,
        "enrollments": enrollments,
        "status_counts": status_counts,
        "avg_attendance": round(stats["avg_attendance"] or 0, 1),
        "avg_score": round(stats["avg_score"] or 0, 1),
        "status_choices": TrainingProgram.Status.choices,
    }
    return render(request, "admin_portal/training/detail.html", context)


@staff_required
def admin_training_edit_view(request, pk):
    """Allows administrators to edit an existing training program."""
    program = get_object_or_404(TrainingProgram, pk=pk)
    form = TrainingProgramForm(request.POST or None, instance=program)
    if request.method == "POST" and form.is_valid():
        program = form.save()
        messages.success(
            request, f"Training program '{program.title}' updated successfully."
        )
        return redirect("admin_training_detail", pk=program.pk)

    context = {
        "program": program,
        "form": form,
        "action_title": f"Edit Training Program: {program.title}",
    }
    return render(request, "admin_portal/training/form.html", context)


@staff_required
@require_POST
def admin_training_delete_view(request, pk):
    """Safely deletes a training program only if no student enrollments exist."""
    program = get_object_or_404(TrainingProgram, pk=pk)
    enrollments_count = program.enrollments.count()
    if enrollments_count > 0:
        messages.error(
            request,
            f"Cannot delete training program '{program.title}' because it has {enrollments_count} "
            f"student enrollment(s). Remove or reassign enrollments first.",
        )
        return redirect("admin_training_detail", pk=program.pk)

    program_title = program.title
    program.delete()
    messages.success(
        request, f"Training program '{program_title}' has been deleted successfully."
    )
    return redirect("admin_training_list")


@staff_required
@require_POST
def admin_training_status_view(request, pk):
    """Quick status update action for training programs."""
    program = get_object_or_404(TrainingProgram, pk=pk)
    new_status = request.POST.get("status")
    if new_status in TrainingProgram.Status.values:
        program.status = new_status
        program.save(update_fields=["status"])
        messages.success(
            request, f"Training program status updated to '{program.get_status_display()}'."
        )
    else:
        messages.error(request, "Invalid status choice selected.")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect("admin_training_detail", pk=program.pk)



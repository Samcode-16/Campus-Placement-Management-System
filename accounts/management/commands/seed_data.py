"""
Fill CPMS with realistic sample data for demos and testing.

    python manage.py seed_data            # add sample data (safe to re-run)
    python manage.py seed_data --reset    # remove previous sample data, then add it again

Only objects created by this command are removed by --reset; your own records are left alone.
All sample accounts share one demo password (printed at the end). Change it before any real use.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Department, StudentProfile
from recruitment.models import (
    Application, Company, InterviewRound, PlacementDrive, PlacementOffer,
)
from training.models import TrainingAttendance, TrainingEnrollment, TrainingProgram

DEMO_PASSWORD = "Cpms@Demo2026"
OFFICER_USERNAME = "officer"

DEPARTMENTS = [
    ("BCA", "Bachelor of Computer Applications", "Three-year undergraduate programme in computer applications."),
    ("BSCCS", "B.Sc. Computer Science", "Undergraduate programme in computer science and mathematics."),
    ("BCOM", "Bachelor of Commerce", "Accounting, taxation and finance."),
    ("BBA", "Bachelor of Business Administration", "Management and entrepreneurship."),
    ("MCA", "Master of Computer Applications", "Postgraduate programme in computer applications."),
    ("MBA", "Master of Business Administration", "Postgraduate programme in management."),
]

# username, first, last, usn, dept, grad year, cgpa, backlogs, phone
STUDENTS = [
    ("anjali",  "Anjali",  "Hegde",    "24UG00101", "BCA",   2027, "8.90", 0, "9845000101"),
    ("rahul",   "Rahul",   "Patil",    "24UG00102", "BCA",   2027, "7.20", 0, "9845000102"),
    ("sneha",   "Sneha",   "Kulkarni", "24UG00103", "BCA",   2027, "6.40", 1, "9845000103"),
    ("vikas",   "Vikas",   "Naik",     "24UG00104", "BCA",   2027, "5.60", 2, "9845000104"),
    ("meghana", "Meghana", "Rao",      "24UG00201", "BSCCS", 2027, "8.10", 0, "9845000201"),
    ("arjun",   "Arjun",   "Shetty",   "24UG00202", "BSCCS", 2027, "6.90", 0, "9845000202"),
    ("pooja",   "Pooja",   "Desai",    "24UG00301", "BCOM",  2027, "8.40", 0, "9845000301"),
    ("kiran",   "Kiran",   "Joshi",    "24UG00302", "BCOM",  2027, "6.10", 1, "9845000302"),
    ("divya",   "Divya",   "Bhat",     "24UG00401", "BBA",   2027, "7.60", 0, "9845000401"),
    ("sachin",  "Sachin",  "Gouda",    "24UG00402", "BBA",   2027, "6.80", 0, "9845000402"),
    ("nikhil",  "Nikhil",  "Reddy",    "24PG00501", "MCA",   2026, "8.30", 0, "9845000501"),
    ("harshita","Harshita","Menon",    "24PG00601", "MBA",   2026, "7.90", 0, "9845000601"),
]

COMPANIES = [
    ("Infosys", "IT Services", "https://www.infosys.com", "Ms. Latha Iyer", "campus@infosys.example.com", "8000000001"),
    ("TCS", "IT Services", "https://www.tcs.com", "Mr. Rohan Mehta", "campus@tcs.example.com", "8000000002"),
    ("Wipro", "IT Services", "https://www.wipro.com", "Ms. Neha Kapoor", "campus@wipro.example.com", "8000000003"),
    ("Tech Mahindra", "IT Services", "https://www.techmahindra.com", "Mr. Sandeep Rao", "campus@techm.example.com", "8000000004"),
    ("HDFC Bank", "Banking", "https://www.hdfcbank.com", "Ms. Priya Nair", "campus@hdfc.example.com", "8000000005"),
    ("Axis Bank", "Banking", "https://www.axisbank.com", "Mr. Anil Kumar", "campus@axis.example.com", "8000000006"),
    ("Larsen & Toubro", "Engineering & Construction", "https://www.larsentoubro.com", "Mr. Suresh Pai", "campus@lnt.example.com", "8000000007"),
    ("Bosch", "Engineering & Manufacturing", "https://www.bosch.in", "Ms. Kavya Shenoy", "campus@bosch.example.com", "8000000008"),
]

now = timezone.now


def days(n, hour=10):
    return (now() + timedelta(days=n)).replace(hour=hour, minute=0, second=0, microsecond=0)


# key, company, title, category, JD, LPA, min cgpa, max backlogs, depts ([] = all), deadline, drive date, status, vacancies
def drive_specs():
    IT = ["BCA", "BSCCS", "MCA"]
    FIN = ["BCOM", "BBA", "MBA"]
    return [
        ("infosys",  "Infosys", "Systems Engineer", "IT", "Develop and test enterprise applications. Training provided. Strong problem solving and basic programming (Java/Python/SQL) required.", "3.60", "6.00", 0, IT, days(7), days(14), "OPEN", 40),
        ("tcs",      "TCS", "SDE-1", "IT", "Build and maintain software modules in an agile team. Knowledge of data structures and one programming language expected.", "7.00", "7.00", 0, IT, days(5), days(12), "OPEN", 15),
        ("wipro",    "Wipro", "Project Engineer", "IT", "Support application development and QA for global clients. Freshers welcome.", "3.50", "6.00", 1, IT, days(9), days(18), "OPEN", 30),
        ("techm",    "Tech Mahindra", "Associate Software Engineer", "IT", "Develop software for telecom clients.", "3.25", "5.50", 2, [], days(-6), days(-2), "CLOSED", 25),
        ("hdfc",     "HDFC Bank", "Relationship Officer", "BANKING", "Acquire and manage retail banking customers. Good communication and sales aptitude required.", "4.20", "6.50", 0, FIN, days(6), days(13), "OPEN", 20),
        ("axis",     "Axis Bank", "Credit Analyst", "BANKING", "Assess loan proposals and prepare credit reports. Finance fundamentals required.", "5.00", "7.00", 0, FIN, days(-30), days(-20), "COMPLETED", 10),
        ("lnt",      "Larsen & Toubro", "Technology Analyst Trainee", "CORE", "Graduate trainee role in digital engineering and automation systems.", "5.50", "7.50", 0, ["BSCCS", "MCA"], days(10), days(21), "OPEN", 12),
        ("bosch",    "Bosch", "Software Trainee", "CORE", "Embedded and enterprise software trainee programme. Aptitude test followed by technical interview.", "6.50", "8.50", 0, ["BCA", "BSCCS", "MCA"], days(12), days(24), "OPEN", 8),
        ("infosys2", "Infosys", "Power Programmer (Upcoming)", "IT", "High-skill programming role. Drive details will be announced shortly.", "8.00", "8.00", 0, ["BCA", "MCA"], days(20), days(30), "DRAFT", 5),
    ]


# student username, drive key, application status, rounds [(type, offset_days, result, remarks)], offer (lpa, accepted) or None
APPLICATIONS = [
    ("anjali",  "infosys", "SHORTLISTED", [("APTITUDE", -1, "CLEARED", "Scored 82%"), ("TECHNICAL", 3, "PENDING", "")], None),
    ("anjali",  "tcs",     "APPLIED",     [], None),
    ("anjali",  "techm",   "SELECTED",    [("APTITUDE", -9, "CLEARED", ""), ("TECHNICAL", -8, "CLEARED", ""), ("HR", -7, "CLEARED", "Good communication")], ("3.25", True)),
    ("rahul",   "infosys", "APPLIED",     [], None),
    ("rahul",   "wipro",   "SHORTLISTED", [("APTITUDE", 4, "PENDING", "")], None),
    ("rahul",   "techm",   "REJECTED",    [("APTITUDE", -9, "CLEARED", ""), ("TECHNICAL", -8, "FAILED", "Needs stronger DSA basics")], None),
    ("sneha",   "wipro",   "APPLIED",     [], None),
    ("sneha",   "techm",   "WITHDRAWN",   [], None),
    ("vikas",   "techm",   "REJECTED",    [("APTITUDE", -9, "FAILED", "")], None),
    ("meghana", "infosys", "APPLIED",     [], None),
    ("meghana", "tcs",     "SHORTLISTED", [("TECHNICAL", 2, "PENDING", "")], None),
    ("meghana", "lnt",     "APPLIED",     [], None),
    ("arjun",   "wipro",   "APPLIED",     [], None),
    ("pooja",   "hdfc",    "SHORTLISTED", [("GD", 2, "PENDING", ""), ("HR", 5, "PENDING", "")], None),
    ("pooja",   "axis",    "SELECTED",    [("GD", -24, "CLEARED", ""), ("HR", -22, "CLEARED", "")], ("5.00", None)),
    ("kiran",   "axis",    "REJECTED",    [("GD", -24, "FAILED", "")], None),
    ("divya",   "hdfc",    "APPLIED",     [], None),
    ("divya",   "axis",    "SELECTED",    [("APTITUDE", -25, "CLEARED", ""), ("HR", -22, "CLEARED", "")], ("5.20", True)),
    ("sachin",  "hdfc",    "APPLIED",     [], None),
    ("nikhil",  "tcs",     "SHORTLISTED", [("APTITUDE", -2, "CLEARED", ""), ("TECHNICAL", 3, "PENDING", "")], None),
    ("nikhil",  "lnt",     "APPLIED",     [], None),
    ("harshita","hdfc",    "SHORTLISTED", [("GD", 2, "PENDING", "")], None),
]

# title, description, trainer, mode, start offset, end offset, capacity, status, sessions
TRAINING = [
    ("Aptitude & Logical Reasoning", "Quantitative aptitude, logical reasoning and verbal ability for online tests.", "Prof. Ramesh Kamat", "OFFLINE", -14, 14, 60, "ONGOING", 8),
    ("Python for Placements", "Python fundamentals, problem solving and coding-round practice.", "Ms. Shruthi Acharya", "ONLINE", 7, 35, 40, "UPCOMING", 0),
    ("Mock Interviews & Group Discussion", "Practice GD and HR/technical interview rounds with feedback.", "Mr. Anand Prabhu (Industry mentor)", "HYBRID", -45, -30, 30, "COMPLETED", 6),
    ("Communication & Soft Skills", "Spoken English, presentation skills and professional etiquette.", "Dr. Lakshmi Bhandari", "OFFLINE", 10, 24, 50, "UPCOMING", 0),
    ("Resume Writing Workshop", "Crafting ATS-friendly resumes and LinkedIn profiles.", "Ms. Deepa Shenoy", "ONLINE", -5, -4, 100, "CANCELLED", 0),
]

# student username, program title, assessment score, completion status
ENROLLMENTS = [
    ("anjali", "Aptitude & Logical Reasoning", "78.50", "IN_PROGRESS"),
    ("rahul", "Aptitude & Logical Reasoning", "64.00", "IN_PROGRESS"),
    ("sneha", "Aptitude & Logical Reasoning", "55.00", "IN_PROGRESS"),
    ("vikas", "Aptitude & Logical Reasoning", "41.50", "IN_PROGRESS"),
    ("pooja", "Aptitude & Logical Reasoning", "81.00", "IN_PROGRESS"),
    ("anjali", "Mock Interviews & Group Discussion", "88.00", "COMPLETED"),
    ("pooja", "Mock Interviews & Group Discussion", "90.00", "COMPLETED"),
    ("kiran", "Mock Interviews & Group Discussion", "52.00", "DROPPED"),
    ("divya", "Mock Interviews & Group Discussion", "79.00", "COMPLETED"),
    ("meghana", "Python for Placements", None, "ENROLLED"),
    ("arjun", "Python for Placements", None, "ENROLLED"),
    ("nikhil", "Python for Placements", None, "ENROLLED"),
    ("sachin", "Communication & Soft Skills", None, "ENROLLED"),
    ("harshita", "Communication & Soft Skills", None, "ENROLLED"),
]


class Command(BaseCommand):
    help = "Create sample departments, users, students, companies, drives, applications, interviews, offers and training data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete earlier sample data before re-creating it.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            self.reset()
        depts = self.make_departments()
        students = self.make_students(depts)
        self.make_officer()
        drives = self.make_drives(depts)
        self.make_applications(students, drives)
        self.make_training(students)
        self.report()

    # ------------------------------------------------------------------
    def reset(self):
        usns = [s[3] for s in STUDENTS]
        names = [c[0] for c in COMPANIES]
        titles = [t[0] for t in TRAINING]
        PlacementOffer.objects.filter(application__student__usn__in=usns).delete()
        Application.objects.filter(student__usn__in=usns).delete()
        TrainingEnrollment.objects.filter(student__usn__in=usns).delete()
        TrainingProgram.objects.filter(title__in=titles).delete()
        d = [x[2] for x in drive_specs()]
        PlacementDrive.objects.filter(company__name__in=names, title__in=d).delete()
        Company.objects.filter(name__in=names, drives__isnull=True).delete()
        User.objects.filter(username__in=[s[0] for s in STUDENTS] + [OFFICER_USERNAME]).delete()
        self.stdout.write("Previous sample data removed.")

    def make_departments(self):
        out = {}
        for code, name, desc in DEPARTMENTS:
            out[code], _ = Department.objects.get_or_create(
                code=code, defaults={"name": name, "description": desc}
            )
        return out

    def make_students(self, depts):
        out = {}
        for uname, first, last, usn, dept, year, cgpa, backlogs, phone in STUDENTS:
            user, created = User.objects.get_or_create(
                username=uname,
                defaults={"first_name": first, "last_name": last, "email": f"{uname}@student.example.com"},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults=dict(usn=usn, department=depts[dept], graduation_year=year,
                              cgpa=Decimal(cgpa), active_backlogs=backlogs, phone=phone),
            )
            if profile.consent_accepted_at is None:  # sample students have "accepted" the policies
                profile.consent_accepted_at = now()
                profile.consent_version = settings.POLICY_VERSION
                profile.save(update_fields=["consent_accepted_at", "consent_version"])
            out[uname] = profile
        return out

    def make_officer(self):
        user, created = User.objects.get_or_create(
            username=OFFICER_USERNAME,
            defaults={"first_name": "Placement", "last_name": "Officer",
                      "email": "officer@college.example.com",
                      "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()

    def make_drives(self, depts):
        companies = {}
        for name, industry, site, person, email, phone in COMPANIES:
            companies[name], _ = Company.objects.get_or_create(
                name=name,
                defaults=dict(industry=industry, website=site, contact_person=person,
                              contact_email=email, contact_phone=phone,
                              description=f"{name} recruits freshers through campus placement drives."),
            )
        drives = {}
        for key, comp, title, cat, jd, lpa, cgpa, backlogs, dcodes, deadline, ddate, status, vac in drive_specs():
            drive, created = PlacementDrive.objects.get_or_create(
                company=companies[comp], title=title,
                defaults=dict(category=cat, job_description=jd, package_lpa=Decimal(lpa),
                              minimum_cgpa=Decimal(cgpa), maximum_backlogs=backlogs,
                              application_deadline=deadline, drive_date=ddate,
                              vacancies=vac, status=status),
            )
            if created:
                drive.eligible_departments.set([depts[c] for c in dcodes])
            drives[key] = drive
        return drives

    def make_applications(self, students, drives):
        for uname, key, status, rounds, offer in APPLICATIONS:
            app, created = Application.objects.get_or_create(
                student=students[uname], drive=drives[key], defaults={"status": status}
            )
            if not created:
                continue
            for rtype, offset, result, remarks in rounds:
                InterviewRound.objects.create(
                    application=app, round_type=rtype, scheduled_at=days(offset, 11),
                    venue="Seminar Hall, Main Block" if rtype != "TECHNICAL" else "Computer Lab 2",
                    result=result, remarks=remarks,
                )
            if offer:
                lpa, accepted = offer
                PlacementOffer.objects.create(
                    application=app, offered_package_lpa=Decimal(lpa),
                    offer_date=date.today() - timedelta(days=5),
                    joining_date=date.today() + timedelta(days=150),
                    accepted=accepted,
                    remarks="Offer letter issued." if accepted is None else "Offer accepted." if accepted else "",
                )

    def make_training(self, students):
        programs = {}
        for title, desc, trainer, mode, s_off, e_off, cap, status, sessions in TRAINING:
            prog, _ = TrainingProgram.objects.get_or_create(
                title=title,
                defaults=dict(description=desc, trainer=trainer, mode=mode,
                              start_date=date.today() + timedelta(days=s_off),
                              end_date=date.today() + timedelta(days=e_off),
                              capacity=cap, status=status),
            )
            programs[title] = (prog, sessions)

        for n, (uname, title, score, status) in enumerate(ENROLLMENTS):
            prog, sessions = programs[title]
            enr, created = TrainingEnrollment.objects.get_or_create(
                student=students[uname], program=prog,
                defaults={"assessment_score": Decimal(score) if score else None,
                          "completion_status": status},
            )
            if not created or sessions == 0:
                continue
            # Attendance: students at the start of the list attend more often
            present = 0
            for i in range(sessions):
                missed = (i + n) % (4 + (n % 3)) == 0
                late = not missed and (i + n) % 5 == 0
                st = "ABSENT" if missed else "LATE" if late else "PRESENT"
                present += st != "ABSENT"
                TrainingAttendance.objects.create(
                    enrollment=enr,
                    session_date=prog.start_date + timedelta(days=i * 2),
                    status=st,
                    remarks="Medical leave" if st == "ABSENT" and i % 2 == 0 else "",
                )
            enr.attendance_percentage = (Decimal(present) / Decimal(sessions) * 100).quantize(Decimal("0.01"))
            enr.save(update_fields=["attendance_percentage"])

    def report(self):
        self.stdout.write(self.style.SUCCESS("\nSample data ready.\n"))
        rows = [
            ("Departments", Department), ("Users", User), ("Student profiles", StudentProfile),
            ("Companies", Company), ("Placement drives", PlacementDrive), ("Applications", Application),
            ("Interview rounds", InterviewRound), ("Offers", PlacementOffer),
            ("Training programs", TrainingProgram), ("Enrollments", TrainingEnrollment),
            ("Attendance records", TrainingAttendance),
        ]
        for label, model in rows:
            self.stdout.write(f"  {label:<20}{model.objects.count()}")
        self.stdout.write(f"\nPlacement officer login : {OFFICER_USERNAME} / {DEMO_PASSWORD}   (/accounts/staff-login/)")
        self.stdout.write(f"Student logins          : anjali, rahul, sneha, ... / {DEMO_PASSWORD}   (/accounts/login/)")

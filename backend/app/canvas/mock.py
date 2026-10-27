"""Fake Canvas data (clearly synthetic) so the whole stack runs without MCPS credentials."""
from .client import CanvasError

COURSES = [
    {"id": 9001, "name": "ENL 5 Period 2 (SAMPLE)", "code": "ENL-5-P2", "term": "2026-27", "html_url": "https://canvas.example.edu/courses/9001"},
    {"id": 9002, "name": "ENL 3 Period 5 (SAMPLE)", "code": "ENL-3-P5", "term": "2026-27", "html_url": "https://canvas.example.edu/courses/9002"},
]
STUDENTS = {
    9001: [
        {"canvas_id": 1001, "name": "Maria Santos", "sortable_name": "Santos, Maria", "sis_id": "123456", "login_id": "msantos"},
        {"canvas_id": 1002, "name": "Joseph Kim", "sortable_name": "Kim, Joseph", "sis_id": "345678", "login_id": "jkim"},
        {"canvas_id": 1004, "name": "Leila Santos", "sortable_name": "Santos, Leila", "sis_id": "900101", "login_id": "lsantos"},
        {"canvas_id": 1005, "name": "Omar Haddad", "sortable_name": "Haddad, Omar", "sis_id": "900102", "login_id": "ohaddad"},
        {"canvas_id": 1006, "name": "Iris Okafor", "sortable_name": "Okafor, Iris", "sis_id": "900103", "login_id": "iokafor"},
        {"canvas_id": 1007, "name": "Diego Flores", "sortable_name": "Flores, Diego", "sis_id": "900104", "login_id": "dflores"},
    ],
    9002: [
        {"canvas_id": 1003, "name": "Amara Okafor", "sortable_name": "Okafor, Amara", "sis_id": "234567", "login_id": "aokafor"},
        {"canvas_id": 1008, "name": "Sofia Tran", "sortable_name": "Tran, Sofia", "sis_id": "900105", "login_id": "stran"},
        {"canvas_id": 1009, "name": "Amir Rahman", "sortable_name": "Rahman, Amir", "sis_id": "900106", "login_id": "arahman"},
        {"canvas_id": 1010, "name": "Nina Patel", "sortable_name": "Patel, Nina", "sis_id": "900107", "login_id": "npatel"},
    ],
}
ASSIGNMENTS = {
    9001: [{"id": 1, "name": "Unit 3 Reading Response", "due_at": "2026-11-05T23:59:00Z", "points": 20,
            "html_url": "https://canvas.example.edu/courses/9001/assignments/1", "description": "Respond to the article using the sentence frames."}],
    9002: [{"id": 2, "name": "Vocabulary Quiz 4", "due_at": "2026-11-02T23:59:00Z", "points": 10,
            "html_url": "https://canvas.example.edu/courses/9002/assignments/2", "description": "Words 31-40."}],
}
PAGES = {
    9001: {"eld-resources": {"title": "ELD Resources (SAMPLE)", "body": "Sentence frames, WIDA can-do descriptors, and bilingual glossaries are linked here.",
                             "html_url": "https://canvas.example.edu/courses/9001/pages/eld-resources"}}
}


class MockCanvasClient:
    base_url = "https://canvas.example.edu"

    async def aclose(self): ...

    async def whoami(self):
        return {"id": 1, "name": "Demo Teacher"}

    async def my_courses(self):
        return COURSES

    async def course_students(self, course_id, search=None):
        studs = STUDENTS.get(int(course_id), [])
        if search:
            q = search.lower()
            studs = [s for s in studs if q in s["name"].lower() or q in s["sis_id"] or q in s["login_id"].lower()]
        return studs

    async def assignments(self, course_id):
        return ASSIGNMENTS.get(int(course_id), [])

    async def pages(self, course_id):
        return [{"url": k, "title": v["title"], "html_url": v["html_url"]} for k, v in PAGES.get(int(course_id), {}).items()]

    async def page(self, course_id, page_url):
        p = PAGES.get(int(course_id), {}).get(page_url)
        if not p:
            raise CanvasError("Page not found")
        return p

    async def custom_columns(self, course_id):
        return [{"id": 77, "title": "Accommodations"}] if int(course_id) == 9001 else []

    async def custom_column_data(self, course_id, column_id):
        return [{"user_id": 1001, "content": "Bilingual glossary; Word bank; Extended time (1.5x)"}]

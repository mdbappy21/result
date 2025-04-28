from fastapi import FastAPI, Query
import requests
from requests.exceptions import RequestException
from typing import Optional

app = FastAPI()

BASE_URL = 'http://software.diu.edu.bd:8006'
TIMEOUT = 20  # Timeout in seconds for all requests

@app.get("/")
def root():
    return {"message": "🎉 DIU Result API is working!"}  # Example: /result?student_id=YOUR_ID

@app.get("/result")
def get_result(student_id: str = Query(...), defense_cgpa: Optional[float] = None):
    # Fetch student info
    try:
        student_info_res = requests.get(
            f"{BASE_URL}/result/studentInfo",
            params={"studentId": student_id},
            timeout=TIMEOUT
        )
        student_info_res.raise_for_status()
    except RequestException:
        return {"error": "Student info request timed out or failed"}

    student_info = student_info_res.json()

    # Fetch semester list
    try:
        semesters_res = requests.get(f"{BASE_URL}/result/semesterList", timeout=TIMEOUT)
        semesters_res.raise_for_status()
    except RequestException:
        return {"error": "Semester list request timed out or failed"}

    semesters = semesters_res.json()

    # Extract starting semesterId from student info
    starting_semester_id = int(student_info.get("semesterId", student_id.split("-")[0]))

    # Filter semesters from student's starting semester onward
    semesters = [s for s in semesters if int(s["semesterId"]) >= starting_semester_id]

    total_credits = 0.0
    weighted_cgpa_sum = 0.0
    semester_data = []

    for semester in semesters:
        semester_id = semester['semesterId']
        try:
            results_res = requests.get(
                f"{BASE_URL}/result",
                params={
                    'studentId': student_id,
                    'semesterId': semester_id,
                    'grecaptcha': ''
                },
                timeout=TIMEOUT
            )
            results_res.raise_for_status()
        except RequestException:
            continue  # Skip if request fails

        results = results_res.json()
        course_list = []

        semester_total_credits = 0.0
        semester_weighted_cgpa_sum = 0.0

        for course in results:
            try:
                credits = float(course['totalCredit'])
                cgpa = float(course['pointEquivalent'])
            except (ValueError, KeyError):
                continue

            total_credits += credits
            weighted_cgpa_sum += cgpa * credits

            semester_total_credits += credits
            semester_weighted_cgpa_sum += cgpa * credits

            course_list.append({
                "title": course.get('courseTitle', 'N/A'),
                "code": course.get('customCourseId', 'N/A'),
                "grade": course.get('gradeLetter', 'N/A'),
                "credits": credits,
                "cgpa": cgpa
            })

        if course_list:  # If there are courses in the semester
            semester_cgpa = round(semester_weighted_cgpa_sum / semester_total_credits, 2) if semester_total_credits > 0 else None
            semester_data.append({
                "semester": f"{semester.get('semesterName', '')} {semester.get('semesterYear', '')}",
                "semesterCGPA": semester_cgpa,
                "semesterCredits": semester_total_credits,  # <-- Added total semester credits here
                "courses": course_list
            })

    # Optional defense credits
    if defense_cgpa is not None:
        defense_credits = 6.0  # Assuming defense/thesis = 6 credits
        total_credits += defense_credits
        weighted_cgpa_sum += defense_cgpa * defense_credits

    final_cgpa = round(weighted_cgpa_sum / total_credits, 2) if total_credits > 0 else None

    return {
        "student": {
            "id": student_info.get("studentId", "Not Provided"),
            "name": student_info.get("studentName", "Not Provided"),
            "program": student_info.get("programName", "Not Provided"),
            "department": student_info.get("departmentName", "Not Provided"),
            "campus": student_info.get("campusName", "Not Provided"),
            "shift": student_info.get("shiftName", "Morning"),
            "faculty": student_info.get("facultyName", "Not Provided"),
            "year": f"{student_info.get('semesterName', '')} {student_info.get('semesterYear', '')}",
            "batch": student_info.get("batchNo", "Not Provided")
        },
        "semesters": semester_data,
        "totalCredits": total_credits,
        "finalCGPA": final_cgpa,
        "defenseIncluded": defense_cgpa is not None
    }

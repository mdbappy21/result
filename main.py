from fastapi import FastAPI, Query
import requests
from requests.exceptions import RequestException
from typing import Optional

app = FastAPI()

BASE_URL = 'http://software.diu.edu.bd:8006'

@app.get("/")
def root():
    return {"message": "🎉 DIU Result API is working! Use /result?student_id=YOUR_ID"}

@app.get("/result")
def get_result(student_id: str = Query(...), defense_cgpa: Optional[float] = None):
    try:
        # Fetch student info
        student_info_res = requests.get(f"{BASE_URL}/result/studentInfo", params={"studentId": student_id})
        student_info_res.raise_for_status()
        student_info = student_info_res.json()
    except RequestException:
        return {"error": "Unable to fetch student info. Please try again later."}

    try:
        # Fetch semesters
        semesters_res = requests.get(f"{BASE_URL}/result/semesterList")
        semesters_res.raise_for_status()
        semesters = semesters_res.json()
    except RequestException:
        return {"error": "Unable to fetch semesters. Please try again later."}

    total_credits = 0
    weighted_cgpa_sum = 0
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
                }
            )
            results_res.raise_for_status()
            results = results_res.json()
        except RequestException:
            continue  # Skip this semester if it fails

        course_list = []
        for course in results:
            try:
                credits = float(course['totalCredit'])
                cgpa = float(course['pointEquivalent'])
            except (KeyError, ValueError):
                continue  # Skip invalid course data

            total_credits += credits
            weighted_cgpa_sum += cgpa * credits

            course_list.append({
                "title": course['courseTitle'],
                "code": course['customCourseId'],
                "grade": course['gradeLetter'],
                "credits": credits,
                "cgpa": cgpa
            })

        semester_data.append({
            "semester": f"{semester['semesterName']} {semester['semesterYear']}",
            "courses": course_list
        })

    # Optional defense
    if defense_cgpa:
        defense_credits = 6.0
        total_credits += defense_credits
        weighted_cgpa_sum += defense_cgpa * defense_credits

    final_cgpa = round(weighted_cgpa_sum / total_credits, 2) if total_credits > 0 else None

    return {
        "student": {
            "id": student_info.get("studentId"),
            "name": student_info.get("studentName"),
            "program": student_info.get("programName"),
            "department": student_info.get("departmentName"),
            "campus": student_info.get("campusName")
        },
        "semesters": semester_data,
        "totalCredits": total_credits,
        "finalCGPA": final_cgpa,
        "defenseIncluded": defense_cgpa is not None
    }

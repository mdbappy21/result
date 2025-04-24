from fastapi import FastAPI, Query
import requests
from requests.exceptions import RequestException
from typing import Optional

app = FastAPI()

BASE_URL = 'http://software.diu.edu.bd:8006'
TIMEOUT = 20  # Timeout in seconds for all requests

@app.get("/")
def root():
    return {"message": "🎉 DIU Result API is working!"} # Use /result?student_id=YOUR_ID

@app.get("/result")
def get_result(student_id: str = Query(...), defense_cgpa: Optional[float] = None):
    # Fetch student info
    try:
        student_info_res = requests.get(
            f"{BASE_URL}/result/studentInfo", 
            params={"studentId": student_id}, 
            timeout=TIMEOUT
        )
    except requests.exceptions.RequestException:
        return {"error": "Student info request timed out or failed"}

    if student_info_res.status_code != 200:
        return {"error": "Student not found or API error"}
    
    student_info = student_info_res.json()

    # Fetch semester list
    try:
        semesters_res = requests.get(f"{BASE_URL}/result/semesterList", timeout=TIMEOUT)
    except requests.exceptions.RequestException:
        return {"error": "Semester list request timed out or failed"}

    if semesters_res.status_code != 200:
        return {"error": "Failed to fetch semesters"}
    
    semesters = semesters_res.json()

    # Extract starting semesterId from student_info (if available)
    starting_semester_id = int(student_info.get("semesterId", student_id.split("-")[0]))

    # Filter semesters from the student's starting semester onward
    semesters = [
        s for s in semesters 
        if int(s["semesterId"]) >= starting_semester_id
    ]

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
                },
                timeout=TIMEOUT
            )
        except requests.exceptions.RequestException:
            continue  # Skip if request fails or times out

        if results_res.status_code != 200:
            continue

        results = results_res.json()
        course_list = []

        for course in results:
            try:
                credits = float(course['totalCredit'])
                cgpa = float(course['pointEquivalent'])
            except (ValueError, KeyError):
                continue

            total_credits += credits
            weighted_cgpa_sum += cgpa * credits

            course_list.append({
                "title": course['courseTitle'],
                "code": course['customCourseId'],
                "grade": course['gradeLetter'],
                "credits": credits,
                "cgpa": cgpa
            })

        if course_list:  # Skip semester if no courses
            semester_data.append({
                "semester": f"{semester['semesterName']} {semester['semesterYear']}",
                "courses": course_list
            })

    # Optional defense credit
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

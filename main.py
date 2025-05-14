from fastapi import FastAPI, Query, HTTPException
import requests
from requests.exceptions import RequestException
from typing import Optional

app = FastAPI()

BASE_URL = 'http://peoplepulse.diu.edu.bd:8189'

@app.get("/")
def root():
    return {"message": "🎉 DIU Result API is working!"}

@app.get("/result")
def get_result(student_id: str = Query(...), defense_cgpa: Optional[float] = None):
    # Fetch student info
    try:
        student_info_res = requests.get(
            f"{BASE_URL}/result/studentInfo",
            params={"studentId": student_id}
        )
        student_info_res.raise_for_status()
    except RequestException:
        raise HTTPException(status_code=504, detail="Failed to fetch student info")

    student_info = student_info_res.json()

    # Fetch semester list
    try:
        semesters_res = requests.get(f"{BASE_URL}/result/semesterList")
        semesters_res.raise_for_status()
    except RequestException:
        raise HTTPException(status_code=504, detail="Failed to fetch semester list")

    semesters = semesters_res.json()

    # Extract starting semesterId from student info
    starting_semester_id = int(student_info.get("semesterId", student_id.split("-")[0]))
    semesters = [s for s in semesters if int(s["semesterId"]) >= starting_semester_id]

    total_credits = 0.0
    passed_credits = 0.0
    weighted_cgpa_sum = 0.0
    semester_data = []
    has_pending_teaching_evaluation = False

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
        except RequestException:
            continue

        results = results_res.json()
        course_list = []

        semester_total_credits = 0.0
        semester_weighted_cgpa_sum = 0.0

        for course in results:
            try:
                credits = float(course['totalCredit'])
                cgpa = float(course['pointEquivalent']) if course['pointEquivalent'] is not None else None
                grade = course.get('gradeLetter', 'N/A')
            except (ValueError, KeyError):
                continue

            total_credits += credits
            semester_total_credits += credits

            if cgpa is not None:
                weighted_cgpa_sum += cgpa * credits
                semester_weighted_cgpa_sum += cgpa * credits

            if grade == 'Teaching evaluation is pending':
                has_pending_teaching_evaluation = True

            if grade != 'F':
                passed_credits += credits

            course_list.append({
                "title": course.get('courseTitle', 'N/A'),
                "code": course.get('customCourseId', 'N/A'),
                "grade": grade,
                "credits": credits,
                "cgpa": cgpa
            })

        semester_cgpa = round(semester_weighted_cgpa_sum / semester_total_credits, 2) if semester_total_credits > 0 else None

        if course_list:
            semester_data.append({
                "semester": f"{semester.get('semesterName', '')} {semester.get('semesterYear', '')}",
                "semesterCGPA": semester_cgpa,
                "semesterCredits": semester_total_credits,
                "courses": course_list
            })

    if defense_cgpa is not None:
        defense_credits = 6.0
        passed_credits += defense_credits
        weighted_cgpa_sum += defense_cgpa * defense_credits

    final_cgpa = round(weighted_cgpa_sum / passed_credits, 2) if passed_credits > 0 else None

    course_status = {}
    low_cgpa_status = {}
    improved_courses = set()

    for semester in semester_data:
        for course in semester["courses"]:
            code = course["code"]
            cgpa = course["cgpa"]
            grade = course["grade"]

            is_fail = (grade == 'F')
            is_low_cgpa = cgpa is not None and cgpa <= 2.5

            if is_fail:
                course_status[code] = {
                    "title": course["title"],
                    "code": code,
                    "grade": grade,
                    "credits": course["credits"]
                }
            else:
                improved_courses.add(code)

            if is_low_cgpa:
                low_cgpa_status[code] = {
                    "title": course["title"],
                    "code": code,
                    "grade": grade,
                    "credits": course["credits"],
                    "cgpa": cgpa
                }

    failed_courses = list(course_status.values())

    low_cgpa_courses = [
        course for code, course in low_cgpa_status.items()
        if code not in course_status or code not in improved_courses
    ]

    passed_course_status = {}

    for semester in semester_data:
        for course in semester["courses"]:
            code = course["code"]
            grade = course["grade"]
            cgpa = course["cgpa"]

            if grade == 'F':
                continue  # skip failed

            if code not in passed_course_status:
                passed_course_status[code] = {
                    "title": course["title"],
                    "code": code,
                    "grade": grade,
                    "credits": course["credits"],
                    "cgpa": cgpa
                }
            else:
                existing_course = passed_course_status[code]
                if cgpa is not None:
                    # Compare CGPA and replace with higher one
                    if cgpa > existing_course["cgpa"]:
                        passed_course_status[code] = {
                            "title": course["title"],
                            "code": code,
                            "grade": grade,
                            "credits": course["credits"],
                            "cgpa": cgpa
                        }
                    elif cgpa == existing_course["cgpa"]:
                        # If CGPAs are equal, keep the latest (newest semester)
                        if existing_course["semesterId"] < course["semesterId"]:
                            passed_course_status[code] = {
                                "title": course["title"],
                                "code": code,
                                "grade": grade,
                                "credits": course["credits"],
                                "cgpa": cgpa,
                                "semesterId": course["semesterId"]
                            }
    passed_courses = list(passed_course_status.values())

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
        "totalCredits": passed_credits,
        "finalCGPA": final_cgpa,
        "defenseIncluded": defense_cgpa is not None,
        "failedCourses": failed_courses,
        "lowCgpaCourses": low_cgpa_courses,
        "passedCourses": passed_courses,
        "hasPendingTeachingEvaluation": has_pending_teaching_evaluation
    }

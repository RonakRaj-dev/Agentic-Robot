import urllib.request
import json

def test_query():
    url = "http://localhost:8000/query"
    payload = {
        "session_id": "test_diagnose_session",
        "student_query": "What this chapter about ?",
        "grade": 9,
        "subject": "Science",
        "chapter": "Chapter 2: Iesc102",
        "student_id": "test_student"
    }
    
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            print("Response Status: 200")
            print("Response Body:")
            print(json.dumps(json.loads(res_body), indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_query()

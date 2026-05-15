import requests
import json
import time

API_URL = "http://localhost:8000/chat"

def run_test_case(name, query):
    print(f"\n{'='*50}")
    print(f"Running Test Case: {name}")
    print(f"Query: {query}")
    print(f"{'='*50}")
    
    try:
        start_time = time.time()
        response = requests.post(API_URL, json={"query": query})
        response.raise_for_status()
        data = response.json()
        end_time = time.time()
        
        print(f"\n[Status]: {data.get('status')}")
        print(f"[Confidence Score]: {data.get('confidence_score', 0.0) * 100:.2f}%")
        print(f"[Action Taken]: {data.get('action')}")
        print(f"[Time Taken]: {end_time - start_time:.2f} seconds")
        
        if data.get('status') == 'success':
            print(f"\n[Final Answer]:\n{data.get('final_answer')}")
        else:
            print(f"\n[Hand-off Summary]:\n{data.get('hand_off_summary')}")
            
        print("\n[Evaluation Details]:")
        print(json.dumps(data.get('evaluation_details'), indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    print("Testing Enterprise Knowledge API...")
    
    # Test 1: Easy question (should have high confidence if we had real DB/LLM)
    # Since we are likely using mocked LLM or local testing without real data, 
    # it might act differently, but this is the structure.
    easy_question = "What is the standard procedure to reset a user's password?"
    run_test_case("Easy Question (High Confidence Expected)", easy_question)
    
    # Test 2: Impossible question (should have low confidence)
    impossible_question = "What did the CEO have for lunch yesterday?"
    run_test_case("Impossible Question (Low Confidence Expected)", impossible_question)

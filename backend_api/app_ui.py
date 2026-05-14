import gradio as gr
import requests

API_URL = "http://localhost:8000/chat"

def chat_interface(query):
    try:
        response = requests.post(API_URL, json={"query": query})
        response.raise_for_status()
        data = response.json()
        
        status = data.get("status")
        confidence = data.get("confidence_score", 0.0)
        
        if status == "success":
            return data.get("final_answer", ""), f"High Confidence ({confidence*100:.2f}%)"
        else:
            return data.get("hand_off_summary", ""), f"Escalated (Confidence: {confidence*100:.2f}%)"
    except Exception as e:
        return f"Error connecting to backend API: {str(e)}", "Error"

demo = gr.Interface(
    fn=chat_interface,
    inputs=gr.Textbox(lines=2, placeholder="Ask a question about enterprise knowledge..."),
    outputs=[gr.Textbox(label="Response"), gr.Textbox(label="Status")],
    title="Enterprise Knowledge Copilot",
    description="Ask questions and get answers from the RAG agent, backed by a Confidence Engine."
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

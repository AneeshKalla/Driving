import uvicorn
import webbrowser
import time
import threading

def open_browser():
    """Open browser after a short delay to ensure server is running"""
    time.sleep(2)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 50)
    print("Starting Driving Analysis Web App")
    print("=" * 50)
    print("\nServer will start at: http://localhost:8000")
    print("Browser will open automatically...\n")

    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Run the FastAPI server
    uvicorn.run(
        "web_app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

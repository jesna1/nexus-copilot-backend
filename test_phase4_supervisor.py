import asyncio
from app.agents.supervisor import supervisor_agent

async def run_phase4_test():
    print("=== Phase 4: Testing Supervisor Agent & Docker Sandbox ===")
    
    # Task that requires code execution & validation
    initial_state = {
        "task": "Write a function that calculates the sum of all prime numbers under 100 and print the result.",
        "code": "",
        "execution_output": "",
        "error": "",
        "retry_count": 0,
        "is_valid": False
    }

    final_state = await supervisor_agent.ainvoke(initial_state)

    print("\n--- FINAL EXECUTION RESULT ---")
    print(f"Task: {final_state['task']}")
    print(f"Code Generated:\n{final_state['code']}")
    print(f"Is Valid: {final_state['is_valid']}")
    print(f"Retries Attempted: {final_state['retry_count']}")
    print(f"Sandbox Output:\n{final_state['execution_output']}")
    if final_state['error']:
        print(f"Final Error: {final_state['error']}")

if __name__ == "__main__":
    asyncio.run(run_phase4_test())
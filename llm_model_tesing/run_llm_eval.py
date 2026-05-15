import json
import time
from openai import OpenAI
from datetime import datetime

# ── CONFIG ──
MODELS = {
    "llama3.1-8b": {"base_url": "http://localhost:11434/v1", "api_key": "not-needed", "model": "llama3.1:8b"},
    "qwen3.5:9b" : {"base_url": "http://localhost:11434/v1", "api_key": "not-needed", "model": "qwen3.5:9b"},
    "gemma4:e4b": {"base_url": "http://localhost:11434/v1", "api_key": "not-needed", "model": "gemma4:e4b"},
}

# ── TOOL DEFINITIONS (OpenAI function-calling format) ──
# This is what was missing. Without this, models never know tools are callable.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_printer_status",
            "description": "Check if the POS printer is connected and working. Returns printer IP, expected IP, spooler status, and any errors.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ip_config",
            "description": "Get the current network IP configuration of the POS device. Use this to diagnose IP mismatch issues.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get POS device system information including OS, app version, RAM, storage, and uptime.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_network",
            "description": "Check network connectivity of the POS device including internet, gateway ping, DNS, and server reachability.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_error_logs",
            "description": "Get recent error logs from the POS application to understand what went wrong.",
            "parameters": {
                "type": "object",
                "properties": {
                    "last_n": {
                        "type": "integer",
                        "description": "Number of recent log entries to return. Default 10.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_printer_ip",
            "description": "Change the printer IP address in POS configuration. Use after diagnosing an IP mismatch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip_address": {
                        "type": "string",
                        "description": "The correct IP address to set for the printer, e.g. '192.168.1.100'",
                    }
                },
                "required": ["ip_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_print_service",
            "description": "Restart the print spooler service on the POS device. Use when printer is connected but not printing.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_pos_app",
            "description": "Restart the ButterPOS application. Use when the app is frozen or crashing.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_app_cache",
            "description": "Clear the POS application cache. Use when the app is slow, frozen, or behaving unexpectedly.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_menu_items",
            "description": "Get all menu items, optionally filtered by category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category to filter by, e.g. 'Rice', 'Burgers'",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_menu_item",
            "description": "Add a new item to the POS menu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the menu item"},
                    "price": {"type": "number", "description": "Price in Rs"},
                    "category": {"type": "string", "description": "Category e.g. 'Rice', 'Drinks'"},
                },
                "required": ["name", "price", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_price",
            "description": "Update the price of an existing menu item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the item to update"},
                    "new_price": {"type": "number", "description": "New price in Rs"},
                },
                "required": ["item_name", "new_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_sales",
            "description": "Get today's sales summary including total orders, revenue, top items, and payment methods.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ── SIMULATED TOOL EXECUTOR ──
# In production this calls your actual MCP server / Android API.
# Here we return the same mock data as butterpos_mcp_server.py.
def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""
    mock_results = {
        "check_printer_status": {
            "printer_connected": False,
            "printer_ip": "192.168.1.50",
            "expected_ip": "192.168.1.100",
            "spooler_running": True,
            "last_print": "2026-03-18 14:30:00",
            "error": "IP address mismatch",
        },
        "get_ip_config": {
            "current_ip": "192.168.1.50",
            "expected_ip": "192.168.1.100",
            "gateway": "192.168.1.1",
            "dns": "8.8.8.8",
            "network_type": "WiFi",
            "signal_strength": "Good",
        },
        "get_system_info": {
            "device": "Samsung Galaxy Tab A8",
            "os": "Android 13",
            "app_version": "3.2.1",
            "ram_available": "2.1 GB",
            "storage_free": "12.4 GB",
            "uptime": "4 days 6 hours",
            "battery": "78%",
        },
        "check_network": {
            "internet": True,
            "gateway_ping": "2ms",
            "dns_resolution": True,
            "pos_server_reachable": True,
            "latency_to_server": "45ms",
        },
        "get_error_logs": {
            "logs": [
                {"time": "14:30:05", "level": "ERROR", "msg": "Printer connection failed: 192.168.1.50 not responding"},
                {"time": "14:30:03", "level": "WARN",  "msg": "IP address changed from 192.168.1.100 to 192.168.1.50"},
                {"time": "14:29:58", "level": "ERROR", "msg": "Print job #4521 failed: printer offline"},
                {"time": "14:25:00", "level": "INFO",  "msg": "Network reconnected"},
                {"time": "14:24:55", "level": "WARN",  "msg": "WiFi signal weak"},
            ]
        },
        "set_printer_ip": {
            "success": True,
            "previous_ip": "192.168.1.50",
            "new_ip": tool_args.get("ip_address", "192.168.1.100"),
            "message": f"Printer IP updated to {tool_args.get('ip_address', '192.168.1.100')}",
        },
        "restart_print_service": {
            "success": True,
            "message": "Print service restarted successfully",
            "printer_status": "online",
        },
        "restart_pos_app": {
            "success": True,
            "message": "POS application restarted",
            "app_status": "running",
            "startup_time": "3.2 seconds",
        },
        "clear_app_cache": {
            "success": True,
            "cache_cleared": "48 MB",
            "message": "Cache cleared successfully",
        },
        "get_menu_items": {
            "items": [
                {"name": "Chicken Biryani", "price": 450, "category": "Rice",    "in_stock": True},
                {"name": "Beef Burger",     "price": 350, "category": "Burgers", "in_stock": True},
                {"name": "Margherita Pizza","price": 800, "category": "Pizza",   "in_stock": False},
                {"name": "Chai",            "price": 80,  "category": "Drinks",  "in_stock": True},
            ],
            "total": 4,
        },
        "add_menu_item": {
            "success": True,
            "item_id": "ITEM-0042",
            "name": tool_args.get("name"),
            "price": tool_args.get("price"),
            "category": tool_args.get("category"),
            "message": f"'{tool_args.get('name')}' added at Rs {tool_args.get('price')} in {tool_args.get('category')}",
        },
        "update_price": {
            "success": True,
            "item": tool_args.get("item_name"),
            "old_price": 350,
            "new_price": tool_args.get("new_price"),
            "message": f"Price of '{tool_args.get('item_name')}' updated to Rs {tool_args.get('new_price')}",
        },
        "get_daily_sales": {
            "date": "2026-03-18",
            "total_orders": 47,
            "total_revenue": 28500,
            "top_items": [
                {"name": "Chicken Biryani", "qty": 15, "revenue": 6750},
                {"name": "Beef Burger",     "qty": 12, "revenue": 4200},
                {"name": "Chai",            "qty": 35, "revenue": 2800},
            ],
            "payment_methods": {"cash": 12500, "card": 14000, "online": 2000},
        },
    }
    result = mock_results.get(tool_name, {"error": f"Unknown tool: {tool_name}"})
    return json.dumps(result)


SYSTEM_PROMPT = """You are a ButterPOS AI support assistant. You help restaurant staff troubleshoot POS system issues autonomously.

Rules:
- If the user writes in Roman Urdu, respond in Roman Urdu
- If the user writes in English, respond in English
- If the user mixes languages, respond in the same mixed style
- ALWAYS use the available tools to diagnose and fix issues yourself — do NOT ask the user to run tools manually
- Diagnose first (check_printer_status, get_ip_config, get_error_logs), then fix (set_printer_ip, restart_print_service, etc.)
- After fixing, confirm what was done and whether the issue is resolved
- Be concise and practical"""


def run_agentic_turn(client, model_name, messages, max_tool_rounds=5):
    """
    Agentic loop: keep calling the model until it stops requesting tool calls.
    Returns (final_text_response, tool_calls_made, total_tokens)
    """
    tool_calls_made = []
    total_tokens = {"input": 0, "output": 0}

    for round_num in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",   # let the model decide when to call tools
            max_tokens=1000,
            temperature=0.3,
        )

        if response.usage:
            total_tokens["input"]  += response.usage.prompt_tokens
            total_tokens["output"] += response.usage.completion_tokens

        choice = response.choices[0]
        msg = choice.message

        # Always append the assistant turn to keep conversation history correct
        messages.append(msg)

        # If no tool calls — model is done
        if not msg.tool_calls:
            return msg.content or "", tool_calls_made, total_tokens

        # Process each tool call the model requested
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments or "{}")

            print(f"      🔧 Tool call: {fn_name}({fn_args})")
            tool_result = execute_tool(fn_name, fn_args)
            print(f"         → {tool_result[:120]}...")

            tool_calls_made.append({"tool": fn_name, "args": fn_args, "result": json.loads(tool_result)})

            # Feed the tool result back as a tool message
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

    # Exhausted max rounds — ask for a final summary
    print(f"      ⚠️  Reached max tool rounds ({max_tool_rounds}), requesting final answer")
    messages.append({"role": "user", "content": "Please summarize what you found and did."})
    final = client.chat.completions.create(
        model=model_name, messages=messages, max_tokens=500, temperature=0.3
    )
    return final.choices[0].message.content or "", tool_calls_made, total_tokens


def test_model(model_name, config, queries):
    """Test a single model with all queries using agentic tool-calling."""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")

    client = OpenAI(base_url=config["base_url"], api_key=config["api_key"])
    results = []

    for i, q in enumerate(queries):
        print(f"\n  [{i+1}/{len(queries)}] ({q['lang']}) {q['query'][:60]}...")

        # Fresh message history per query
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": q["query"]},
        ]

        start = time.time()
        try:
            answer, tool_calls, tokens = run_agentic_turn(client, config["model"], messages)
            latency = round(time.time() - start, 2)

            print(f"    Latency: {latency}s | Tokens: {tokens['input']}+{tokens['output']} | Tools used: {len(tool_calls)}")
            print(f"    Response: {answer[:300]}...")

            results.append({
                "query":           q["query"],
                "language":        q["lang"],
                "category":        q["category"],
                "response":        answer,
                "tool_calls":      tool_calls,
                "tools_used":      [tc["tool"] for tc in tool_calls],
                "latency_seconds": latency,
                "tokens_input":    tokens["input"],
                "tokens_output":   tokens["output"],
                "error":           None,
            })

        except Exception as e:
            latency = round(time.time() - start, 2)
            print(f"    ERROR: {str(e)[:120]}")
            results.append({
                "query":           q["query"],
                "language":        q["lang"],
                "category":        q["category"],
                "response":        None,
                "tool_calls":      [],
                "tools_used":      [],
                "latency_seconds": latency,
                "tokens_input":    0,
                "tokens_output":   0,
                "error":           str(e),
            })

    return results


def run_evaluation():
    """Run full evaluation across all models."""
    all_results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for model_name, config in MODELS.items():
        try:
            results = test_model(model_name, config, QUERIES)
            all_results[model_name] = results
        except Exception as e:
            print(f"\n  SKIPPED {model_name}: {e}")
            continue

    output_file = f"llm_eval_results_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_file}")

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")

    for model_name, results in all_results.items():
        successful   = [r for r in results if r["error"] is None]
        avg_latency  = sum(r["latency_seconds"] for r in successful) / len(successful) if successful else 0
        total_tokens = sum(r["tokens_input"] + r["tokens_output"] for r in successful)
        tool_usage   = [tc for r in successful for tc in r["tools_used"]]

        from collections import Counter
        top_tools = Counter(tool_usage).most_common(5)

        print(f"\n{model_name}:")
        print(f"  Success rate : {len(successful)}/{len(results)}")
        print(f"  Avg latency  : {avg_latency:.2f}s")
        print(f"  Total tokens : {total_tokens}")
        print(f"  Total tool calls made: {len(tool_usage)}")
        print(f"  Top tools used: {top_tools}")
        print(f"  English queries : {len([r for r in successful if r['language'] == 'en'])}")
        print(f"  Roman Urdu queries: {len([r for r in successful if r['language'] == 'ur'])}")
        print(f"  Mixed queries   : {len([r for r in successful if r['language'] == 'mixed'])}")


# ── TEST QUERIES ──
QUERIES = [
    {"query": "mera POS bill print nahi kar raha kya karun", "lang": "ur", "category": "printer"},
    # {"query": "pehle bill print nahi ho raha tha, phir restart kiya, ab screen freeze ho gayi", "lang": "mixed", "category": "software"},
    # {"query": "I changed the WiFi password and now POS can't connect, also printer went offline", "lang": "en", "category": "network"},
]

if __name__ == "__main__":
    run_evaluation()
"""ReAct Loop - Reasoning + Acting loop for autonomous agent behavior."""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.agent.tools import get_agent_tools
from src.agent.tool_executor import ToolExecutor


@dataclass
class ReActStep:
    """A single step in the ReAct loop."""
    step_number: int
    action_type: str  # "thought", "tool_call", "observation", "final_answer"
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None


class ReActLoop:
    """Implements the Reasoning + Acting loop for autonomous tool use.
    
    The loop:
    1. LLM receives prompt + tool definitions
    2. LLM decides: call a tool or give final answer
    3. If tool call: execute tool, add observation, repeat
    4. If final answer: return result
    """
    
    def __init__(
        self, 
        client,  # GeminiClient
        executor: ToolExecutor,
        max_iterations: int = 5,
        verbose: bool = True
    ):
        self.client = client
        self.executor = executor
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.tools = get_agent_tools()
        self.history: List[ReActStep] = []
    
    async def run(self, initial_prompt: str, thinking_budget: int = 8192, max_tokens: int = 16384) -> str:
        """Run the ReAct loop until completion or max iterations.
        
        Args:
            initial_prompt: The initial analysis prompt
            thinking_budget: Token budget for thinking (Gemini 2.5)
            max_tokens: Max output tokens (must be > thinking_budget for full response)
            
        Returns:
            Final analysis content
        """
        if self.verbose:
            print(f"\n[ReAct] Starting loop (max {self.max_iterations} iterations)")
        
        # Build conversation history
        conversation = [
            {"role": "user", "content": initial_prompt}
        ]
        
        for i in range(self.max_iterations):
            if self.verbose:
                print(f"\n[ReAct] Iteration {i + 1}/{self.max_iterations}")
            
            # Call LLM with tools
            response = self.client.generate_with_tools(
                messages=conversation,
                tools=self.tools,
                thinking_budget=thinking_budget,
                max_tokens=max_tokens,
            )
            
            # Print thoughts if available
            if self.verbose and response.thoughts:
                print("\n" + "-"*30)
                print("[Agent Intelligence - THINKING]")
                print("-"*30)
                print(response.thoughts)
                print("-"*30 + "\n")
            
            # Check if response contains a function call
            if response.function_call:
                fc = response.function_call
                
                if self.verbose:
                    print(f"[ReAct] Tool Call: {fc.name}({fc.args})")
                
                # Record the tool call
                self.history.append(ReActStep(
                    step_number=i + 1,
                    action_type="tool_call",
                    content=f"Calling {fc.name}",
                    tool_name=fc.name,
                    tool_args=dict(fc.args) if hasattr(fc.args, 'items') else fc.args
                ))
                
                # Execute the tool
                observation = await self.executor.execute(fc)
                
                if self.verbose:
                    print(f"[ReAct] Observation: {observation[:200]}...")
                
                # Record observation
                self.history.append(ReActStep(
                    step_number=i + 1,
                    action_type="observation",
                    content=observation
                ))
                
                # Add to conversation: assistant's function call + function result
                conversation.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": {"name": fc.name, "arguments": fc.args}
                })
                conversation.append({
                    "role": "function",
                    "name": fc.name,
                    "content": observation
                })
                
                continue  # Next iteration
            
            # No function call = final answer
            if self.verbose:
                print(f"[ReAct] Final answer received ({len(response.content)} chars)")
            
            self.history.append(ReActStep(
                step_number=i + 1,
                action_type="final_answer",
                content=response.content[:100] + "..."
            ))
            
            return response.content
        
        # Max iterations reached
        if self.verbose:
            print(f"[ReAct] Max iterations ({self.max_iterations}) reached")
        
        return f"[Analysis incomplete - reached max {self.max_iterations} tool calls]\n\n" + (
            conversation[-1].get("content", "No final content") 
            if conversation else "No response"
        )
    
    def get_trace(self) -> List[Dict]:
        """Get the execution trace for debugging/logging."""
        return [
            {
                "step": s.step_number,
                "type": s.action_type,
                "tool": s.tool_name,
                "content_preview": s.content[:100] if s.content else None
            }
            for s in self.history
        ]


async def run_react_analysis(
    client,
    executor: ToolExecutor,
    prompt: str,
    max_iterations: int = 5,
    thinking_budget: int = 8192,
    max_tokens: int = 16384,
    verbose: bool = True
) -> str:
    """Convenience function to run a ReAct analysis.
    
    Args:
        client: GeminiClient instance
        executor: ToolExecutor instance
        prompt: The analysis prompt
        max_iterations: Max tool calls before stopping
        thinking_budget: Token budget for thinking
        max_tokens: Max output tokens (should be > thinking_budget)
        verbose: Print progress
        
    Returns:
        Final analysis content
    """
    loop = ReActLoop(
        client=client,
        executor=executor,
        max_iterations=max_iterations,
        verbose=verbose
    )
    
    result = await loop.run(prompt, thinking_budget=thinking_budget, max_tokens=max_tokens)
    
    if verbose:
        print(f"\n[ReAct] Trace: {loop.get_trace()}")
    
    return result

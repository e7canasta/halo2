"""Tool execution pipeline with pre/post filters.

Orchestrates complete tool execution flow with quality-first approach:
ALL pre-filters execute → validation → execution → ALL post-filters execute
"""

from .filters import (
    FilterChain,
    FilterStage,
    SchemaValidator,
    ContextEnricher,
    ParameterNormalizer,
    ResultValidator,
    ContextUpdater,
    NLGFormatter,
)
from .executor import execute_tool, ToolCallError
import logging

logger = logging.getLogger(__name__)


class ToolExecutionPipeline:
    """Complete tool execution pipeline with filters.

    Philosophy: QUALITY > SPEED
    - ALL pre-filters run (no early return)
    - Comprehensive validation before execution
    - ALL post-filters run for learning and formatting
    """

    def __init__(self, enable_nlg: bool = True, conversation_manager=None):
        """Initialize pipeline with default filters.

        Args:
            enable_nlg: Enable NLG formatting in post-execution
            conversation_manager: Optional ConversationContextManager for context enrichment
        """
        # Pre-execution filters (run before tool execution)
        self.pre_filters = FilterChain(
            FilterStage.PRE_EXECUTION,
            [
                SchemaValidator(),  # 1. Validate schema
                ParameterNormalizer(),  # 2. Normalize params
                ContextEnricher(context_manager=conversation_manager),  # 3. Enrich with context
            ],
        )

        # Post-execution filters (run after tool execution)
        self.post_filters = FilterChain(
            FilterStage.POST_EXECUTION,
            [
                ResultValidator(),  # 1. Validate result format
                NLGFormatter(enable_nlg=enable_nlg),  # 2. Format as NLG
                ContextUpdater(),  # 3. Update context
            ],
        )

    def execute(self, tool_name: str, parameters: dict, context: dict = None) -> dict:
        """Execute tool with full filter pipeline.

        Args:
            tool_name: Tool to execute
            parameters: Tool parameters
            context: Conversation context (will be updated in-place)

        Returns:
            Complete result dict with:
            - result: Tool execution result
            - context_updates: Context updates to apply
            - metadata: Filter metadata (validation, normalization, etc.)

        Raises:
            ToolCallError: If validation fails or execution errors
        """
        context = context or {}
        metadata = {"pre_filters": {}, "post_filters": {}}

        # === PRE-EXECUTION FILTERS ===
        logger.info(f"Running pre-filters for {tool_name}")

        pre_data = {"tool_name": tool_name, "parameters": parameters}
        pre_result = self.pre_filters.apply(pre_data, context)

        metadata["pre_filters"] = pre_result.metadata

        # Check if any pre-filter rejected
        if pre_result.action == "reject":
            error_msg = pre_result.error_message or "Pre-filter validation failed"
            logger.error(f"Pre-filter rejected: {error_msg}")
            raise ToolCallError(error_msg)

        # Use modified parameters if any filter modified them
        final_params = pre_result.modified_data["parameters"] if pre_result.action == "modify" else parameters

        logger.info(f"Pre-filters passed, executing tool: {tool_name}")

        # === TOOL EXECUTION ===
        try:
            execution_result = execute_tool(tool_name, final_params)
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            # Even on error, run through post-filters for consistency
            execution_result = {
                "status": "error",
                "message": str(e),
                "device_state": {},
            }

        # === POST-EXECUTION FILTERS ===
        logger.info(f"Running post-filters for {tool_name}")

        post_data = {
            "result": execution_result,
            "tool_name": tool_name,
            "parameters": final_params,
        }
        post_result = self.post_filters.apply(post_data, context)

        metadata["post_filters"] = post_result.metadata

        # Extract final result and context updates
        final_result = post_result.modified_data["result"] if post_result.action == "modify" else execution_result

        # Extract context updates from ContextUpdater metadata
        context_updates = {}
        if "context_updates" in post_result.metadata:
            context_updates = post_result.metadata["context_updates"]

        logger.info(f"Pipeline completed for {tool_name}")

        return {
            "result": final_result,
            "context_updates": context_updates,
            "metadata": metadata,
        }

    def add_pre_filter(self, filter, position: int = -1):
        """Add a pre-execution filter.

        Args:
            filter: Filter instance
            position: Position in chain (-1 = end)
        """
        self.pre_filters.add_filter(filter, position)

    def add_post_filter(self, filter, position: int = -1):
        """Add a post-execution filter.

        Args:
            filter: Filter instance
            position: Position in chain (-1 = end)
        """
        self.post_filters.add_filter(filter, position)

    def remove_pre_filter(self, name: str):
        """Remove a pre-execution filter by name."""
        self.pre_filters.remove_filter(name)

    def remove_post_filter(self, name: str):
        """Remove a post-execution filter by name."""
        self.post_filters.remove_filter(name)


# Global pipeline instance (legacy, without conversation manager)
_pipeline: ToolExecutionPipeline | None = None


def get_pipeline(enable_nlg: bool = True, conversation_manager=None) -> ToolExecutionPipeline:
    """Get pipeline instance.

    Args:
        enable_nlg: Enable NLG formatting
        conversation_manager: Optional ConversationContextManager

    Returns:
        ToolExecutionPipeline instance
        - If conversation_manager is provided, creates a new instance
        - Otherwise returns singleton for backward compatibility
    """
    global _pipeline

    # If conversation_manager provided, always create new instance
    if conversation_manager is not None:
        return ToolExecutionPipeline(enable_nlg=enable_nlg, conversation_manager=conversation_manager)

    # Legacy: singleton without conversation manager
    if _pipeline is None:
        _pipeline = ToolExecutionPipeline(enable_nlg=enable_nlg)
    return _pipeline

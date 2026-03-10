.PHONY: test server install chat install-spacy train-ner stats-dataset clean convert-golden train-functiongemma eval-functiongemma setup-gemini show-gemini-config test-gemini test-gemini-agent test-scenarios test-scenarios-verbose test-scenario test-context

install:
	uv sync
	uv pip install -e .

install-spacy:
	@echo "Downloading spaCy Spanish model..."
	uv run python -m spacy download es_core_news_md

test:
	uv run python test/test_halo_qwen.py

server:
	uv run python src/halo/api/server.py

chat:
	uv run python src/halo/chat.py

# NER training and dataset commands
train-ner:
	uv run python -m halo.nlp.training.trainer

stats-dataset:
	uv run python -m halo.nlp.training.stats

clean:
	rm -rf .ruff_cache __pycache__ src/halo/__pycache__ models/ner_custom models/.checkpoint

# FunctionGemma commands
convert-golden:
	@echo "Converting golden dataset to FunctionGemma format..."
	uv run python scripts/convert_golden_to_fg.py --stats

train-functiongemma:
	@echo "Fine-tuning FunctionGemma with Halo dataset..."
	uv run python scripts/finetune_functiongemma.py --epochs 3

train-functiongemma-quick:
	@echo "Quick fine-tuning (1 epoch) for testing..."
	uv run python scripts/finetune_functiongemma.py --epochs 1

eval-functiongemma:
	@echo "Evaluating FunctionGemma model..."
	uv run python scripts/eval_functiongemma.py

# Gemini (Yoda) commands
setup-gemini:
	@echo "Setting up Gemini API key..."
	./scripts/setup_gemini.sh

show-gemini-config:
	@echo "Showing Gemini model configuration..."
	uv run python scripts/show_gemini_config.py

test-gemini:
	@echo "Testing Gemini classifier..."
	uv run python test/test_gemini_classifier.py

test-gemini-agent:
	@echo "Testing Gemini Agent (3 roles)..."
	uv run python -m pytest test/test_gemini_agent.py test/test_model_config.py -v

# Scenario testing (conversational flows)
test-scenarios:
	@echo "Running all scenario tests..."
	uv run python test/scenario_tester.py test/scenarios/

test-scenarios-verbose:
	@echo "Running scenario tests (verbose)..."
	uv run python test/scenario_tester.py test/scenarios/ -v

test-scenario:
	@echo "Running specific scenario: $(SCENARIO)"
	uv run python test/scenario_tester.py test/scenarios/$(SCENARIO).yaml -v

test-context:
	@echo "Testing ConversationContextManager..."
	uv run python -m pytest test/test_conversation_context.py -v
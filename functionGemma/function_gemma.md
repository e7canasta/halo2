<br />

FunctionGemma is a specialized version of our Gemma 3 270M model tuned for function calling. It is designed as a strong base for further training into custom, fast, private, local agents that translate natural language into executable API actions.

## When to choose FunctionGemma

FunctionGemma is the bridge between natural language and software execution. It is the right tool if:

- **You have a defined API surface:**Your application has a defined set of actions (e.g., smart home, media, navigation).
- **You are ready to fine-tune:**You need the consistent, deterministic behavior that comes from fine-tuning on specific data, rather than the variability of zero-shot prompting.
- **You prioritize local-first deployment:**Your application requires near-instant latency and total data privacy, running efficiently within the compute and battery limits of edge devices.
- **You are building compound systems:**You need a lightweight edge model to handle local actions, allowing your system to process common commands on-device and only query larger models (like Gemma 3 27B) for more complex tasks.

[Get it on Hugging Face](https://huggingface.co/google/functiongemma-270m-it)[Get it on Kaggle](https://www.kaggle.com/models/google/functiongemma)[Access it on Vertex](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/functiongemma)

As with other Gemma models, FunctionGemma is provided with open weights and licensed for responsible[commercial use](https://ai.google.dev/gemma/terms), allowing you to fine tune and deploy it in your own projects and applications.

[Formatting and best practices](https://ai.google.dev/gemma/docs/functiongemma/formatting-and-best-practices)[Try FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/function-calling-with-hf)

[Fine-tune FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma)[Fine-tune the Mobile Actions demo](https://ai.google.dev/gemma/docs/mobile-actions)


<br />

FunctionGemma is a specialized version of the Gemma 3 270M model, trained specifically for**function calling**(i.e., tool use).

To manage the interaction between natural language instructions and structured, tool-related data, FunctionGemma uses a specific set of formatting control tokens. These tokens are essential for the model to distinguish between conversation and data, and to understand tool definitions, tool calls, and tool results.

## Base Prompt Structure

FunctionGemma builds on the[Gemma prompt structure](https://ai.google.dev/gemma/docs/core/prompt-structure), using`<start_of_turn>role`and`<end_of_turn>`to describe conversational turns. The`role`is typically`user`or`model`(and sometimes`developer`for providing initial context, as seen below).

The function-specific tokens are used*within*these turns to structure the tool-related information.

### Control Tokens

FunctionGemma is trained on six special tokens to manage the "tool use" lifecycle.

|                         Token Pair                          |                   Purpose                   |
|-------------------------------------------------------------|---------------------------------------------|
| `<start_function_declaration>` `<end_function_declaration>` | Defines a tool.                             |
| `<start_function_call>` `<end_function_call>`               | Indicates a model's request to use a tool.  |
| `<start_function_response>` `<end_function_response>`       | Provides a tool's result back to the model. |

> NOTE:`<start_function_response>`is an additional stop sequence for the inference engine.

### Delimiter for String Values:`<escape>`

A single token,`<escape>`, is used as a delimiter for**all string values**within the structured data blocks.

- **Purpose:** This token ensures that any special characters (like`{`,`}`,`,`, or quotes) inside a string are treated as literal text and not as part of the data structure's syntax.
- **Usage:** All string literals in your function declarations, calls, and responses must be enclosed, like:`key:<escape>string value<escape>`.

## Training Scope and Limitations

FunctionGemma is trained for specific types of agentic workflows. It is important to understand the model's training context to ensure reliability in production environments.

### Supported Workflows

The model has been explicitly trained on**Single Turn** and**Parallel**function calling.

- **Single Turn:**The user provides a query, and the model selects a single tool to address it.
- **Parallel:**The user provides a query containing multiple independent requests, and the model generates multiple tool calls simultaneously.

**Example: Parallel (Supported)**
> **User:**"What is the weather in Tokyo and what is the stock price of Google?"

The model generates calls for`get_weather(Tokyo)`and`get_stock_price(GOOG)`in a single response. These actions don't depend on each other.

### Unsupported Workflows

The model has**not** been explicitly trained on**Multi-Turn** or**Multi-Step**workflows.
> **Note:**We expect the model to be able to generalize a bit to these scenarios, especially if fine-tuned on specific use cases, but it has not been trained to perform these tasks out of the box.

- **Multi-Step (Chaining):**Scenarios where the output of one tool is required as the argument for a subsequent tool.

  - **Example:**"Roll a die with 20 sides and check if the number is prime."
  - **Complexity:** This requires rolling a die first (Tool A), and*then*using the result to check if the number is prime (Tool B). FunctionGemma is not trained to reason through this dependency chain automatically.
- **Multi-Turn:**Scenarios requiring the model to maintain state or context over a long back-and-forth conversation to determine tool parameters.

> **User:** "Book me a table."  
> **Model:** "For how many people?"  
> **User:**"Four."

- **Complexity:** The model is not explicitly trained to aggregate these separate turns into a final`book_table(people=4)`call without external state management.

### Semantic Nuances

The model may sometimes miss the relationship between semantically related concepts if the user's prompt is abstract or indirect.

Here's an example function.  

    def get_current_temperature(location: str, unit: str):
        """
        Get the current temperature at a location.

        Args:
            location: The location to get the temperature for.
            unit: The unit to return the temperature in. (choices: ["celsius", "fahrenheit"])
        """
        return 22.0

For example, concepts like "cold" or "hot" imply temperature, but might not immediately trigger a specific tool named`get_current_temperature`if the model does not make the semantic connection in that specific context.

- **Mitigation Strategies:**
  - **Enriched Tool Definition:**This is often the most effective fix. Expanding the function's description to include semantic keywords helps the model bridge the gap. For example, adding "This function can be used to determine if the weather is hot or cold in a given location" to the docstring allows FunctionGemma to correctly map those qualitative descriptors to the tool.
  - **Prompt Engineering:**Making the user query more detailed or explicit can help the model trigger the correct tool, though this relies on user behavior.
  - **Fine-tuning:** For production environments where users frequently use highly indirect language (e.g., "is it nice out?" versus "get weather"), we recommend[fine-tuning](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma)the model on a dataset that explicitly maps these semantic nuances to the correct tool definitions.

**Example: Make Semantic Connection**
> **User:**"Hey, is it cold in Paris right now?"

**Scenario A: Limited Description** If the tool description is just`Get the
current temperature at a location.`, the model might fail to associate "cold" with get_current_temperature and respond that it cannot provide weather information.

**Scenario B: Enriched Description** If the tool description is updated to include:`Get the current temperature at a location. This function can be used
to determine if the weather is hot or cold in a given location.`, the model successfully makes the connection:  
`<start_function_call>call:get_current_temperature{location:<escape>Paris<escape>,unit:<escape>celsius<escape>}<end_function_call>`

## Example: Weather Tool Flow

Here is a complete, step-by-step formatted example demonstrating the flow for using the`get_current_weather`tool.

![A diagram of Weather Tool Flow](https://ai.google.dev/gemma/docs/images/functiongemma_flow.png)

### Turn 1: Tool Definition (Developer)

First, you provide the model with the definitions of all available tools. This is done as the first turn from a`developer`role. This block is used to provide the model with the "schema" of an available function, including its name, a description of what it does, and its parameters.

It is important to include the system prompt`You are a model that can do
function calling with the following functions`to enable the model to call tools. This phrase acts as a prompt-based trigger to switch between tooling capability and general conversation.  

```
<start_of_turn>developer
You are a model that can do function calling with the following functions<start_function_declaration>declaration:get_current_weather{description:<escape>Gets the current weather in a given location.<escape>,parameters:{properties:{location:{description:<escape>The city and state, e.g. "San Francisco, CA" or "Tokyo, JP"<escape>,type:<escape>STRING<escape>},unit:{description:<escape>The unit to return the temperature in.<escape>,enum:[<escape>celsius<escape>,<escape>fahrenheit<escape>],type:<escape>STRING<escape>}},required:[<escape>location<escape>],type:<escape>OBJECT<escape>}}<end_function_declaration><end_of_turn>
```

### Turn 2: User Prompt (User)

Next, the user asks a question that requires the tool you just defined.  

    <start_of_turn>user
    Hey, what's the weather in Tokyo right now?<end_of_turn>

### Turn 3: Model Issues Function Call (Model)

The model processes the user's request and the tool definition. It determines it needs to call the`get_current_weather`function and outputs the following turn.  

    <start_function_call>call:get_current_weather{location:<escape>Tokyo, Japan<escape>}<end_function_call>

> **Application Logic:** At this point, your application must intercept this output. Instead of displaying it to the user, you parse the function call (e.g.,`get_current_weather(location="Tokyo, Japan")`), execute this function in your own code, and get the result (e.g., a JSON object).

### Turn 4: Application Provides Function Response (Developer)

You now send the return value from your function back to the model. This turn uses the function response tokens.  

    <start_function_response>response:get_current_weather{temperature:15,weather:<escape>sunny<escape>}<end_function_response>

### Turn 5: Model Generates Final Answer (Model)

The model receives the function's result from Turn 4. It now has all the information needed to answer the user's original question from Turn 2. It processes this new context and generates the final, natural language response.  

    The current weather in Tokyo is sunny with a temperature of 15 degrees Celsius.<end_of_turn>

You can see more complete version of this example in the[Full function calling sequence with FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/full-function-calling-sequence-with-functiongemma)


<br />

|---|---|---|---|---|
| [![](https://ai.google.dev/static/site-assets/images/docs/notebook-site-button.png)View on ai.google.dev](https://ai.google.dev/gemma/docs/functiongemma/function-calling-with-hf) | [![](https://www.tensorflow.org/images/colab_logo_32px.png)Run in Google Colab](https://colab.research.google.com/github/google-gemini/gemma-cookbook/blob/main/docs/functiongemma/function-calling-with-hf.ipynb) | [![](https://www.kaggle.com/static/images/logos/kaggle-logo-transparent-300.png)Run in Kaggle](https://kaggle.com/kernels/welcome?src=https://github.com/google-gemini/gemma-cookbook/blob/main/docs/functiongemma/function-calling-with-hf.ipynb) | [![](https://ai.google.dev/images/cloud-icon.svg)Open in Vertex AI](https://console.cloud.google.com/vertex-ai/colab/import/https%3A%2F%2Fraw.githubusercontent.com%2Fgoogle-gemini%2Fgemma-cookbook%2Fmain%2Fdocs%2Ffunctiongemma%2Ffunction-calling-with-hf.ipynb) | [![](https://www.tensorflow.org/images/GitHub-Mark-32px.png)View source on GitHub](https://github.com/google-gemini/gemma-cookbook/blob/main/docs/functiongemma/function-calling-with-hf.ipynb) |

FunctionGemma is a specialized version of the Gemma 3 270M model, trained specifically for function calling improvements. It has the same architecture as Gemma, but uses a different chat format and tokenizer.

This guide shows the process of using FunctionGemma within the Hugging Face ecosystem. It covers essential setup steps, such as installing the `torch` and `transformers` libraries and loading the model using `AutoProcessor` and `AutoModelForCausalLM`. Additionally, the guide explains how to pass tools to the model using either manual JSON schemas or raw Python functions and advises on when to use manual schemas to handle complex custom objects effectively.

## Setup

Before starting this tutorial, complete the following steps:

- Get access to FunctionGemma by logging into [Hugging Face](https://huggingface.co/google/functiongemma-270m-it) and selecting **Acknowledge license** for a FunctionGemma model.
- Generate a Hugging Face [Access Token](https://huggingface.co/docs/hub/en/security-tokens#how-to-manage-user-access-token) and add it to your Colab environment.

This notebook will run on either CPU or GPU.

## Install Python packages

Install the Hugging Face libraries required for running the FunctionGemma model and making requests.

    # Install PyTorch & other libraries
    pip install torch

    # Install the transformers library
    pip install transformers

After you have accepted the license, you need a valid Hugging Face Token to access the model.

    # Login into Hugging Face Hub
    from huggingface_hub import login
    login()

## Load Model

Use the `torch` and `transformers` libraries to create an instance of a `processor` and `model` using the `AutoProcessor` and `AutoModelForCausalLM` classes as shown in the following code example:

    from transformers import AutoProcessor, AutoModelForCausalLM

    GEMMA_MODEL_ID = "google/functiongemma-270m-it"

    processor = AutoProcessor.from_pretrained(GEMMA_MODEL_ID, device_map="auto")
    model = AutoModelForCausalLM.from_pretrained(GEMMA_MODEL_ID, dtype="auto", device_map="auto")

## Passing tools

You can pass tools to the model using the `apply_chat_template()` function via the `tools` argument. There are two methods for defining these tools:

- **JSON schema**: You can manually construct a JSON dictionary defining the function name, description, and parameters (including types and required fields).
- **Raw Python Functions** : You can pass actual Python functions. The system automatically generates the required JSON schema by parsing the function's type hints, arguments, and docstrings. For best results, docstrings should adhere to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

Below is the example with the JSON schema.

    weather_function_schema = {
        "type": "function",
        "function": {
            "name": "get_current_temperature",
            "description": "Gets the current temperature for a given location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name, e.g. San Francisco",
                    },
                },
                "required": ["location"],
            },
        }
    }

    message = [
        # ESSENTIAL SYSTEM PROMPT:
        # This line activates the model's function calling logic.
        {
            "role": "developer", "content": "You are a model that can do function calling with the following functions"
        },
        {
            "role": "user", "content": "What's the temperature in London?"
        }
    ]

    inputs = processor.apply_chat_template(message, tools=[weather_function_schema], add_generation_prompt=True, return_dict=True, return_tensors="pt")

    out = model.generate(**inputs.to(model.device), pad_token_id=processor.eos_token_id, max_new_tokens=128)
    output = processor.decode(out[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)

    print(f"Output: {output}")

```
Output: <start_function_call>call:get_current_temperature{location:<escape>London<escape>}<end_function_call>
```
>
> > [!NOTE]
> > **Note:** To ensure FunctionGemma correctly interprets the available tools and generates a structured call instead of plain text, the **developer** message is essential. This specific system prompt instructs the model that it has permission and capability to perform function calling.
>
    message = [
            # ESSENTIAL SYSTEM PROMPT:
            # This line activates the model's function calling logic.
            {"role": "developer", "content": "You are a model that can do function calling with the following functions"},
            {"role": "user", "content": prompt},
    ]

And the same example with the raw Python function.

    def get_current_temperature(location: str):
        """
        Gets the current temperature for a given location.

        Args:
            location: The city name, e.g. San Francisco
        """
        return "15°C"

    message = [
        {
            "role": "user", "content": "What's the temperature in London?"
        }
    ]

    inputs = processor.apply_chat_template(message, tools=[weather_function_schema], add_generation_prompt=True, return_dict=True, return_tensors="pt")

    out = model.generate(**inputs.to(model.device), pad_token_id=processor.eos_token_id, max_new_tokens=128)
    output = processor.decode(out[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)

    print(f"Output: {output}")

```
Output: <start_function_call>call:get_current_temperature{location:<escape>London<escape>}<end_function_call>
```

## Important Caveat: Automatic vs. Manual Schemas

When relying on automatic conversion from Python functions to JSON schema, the generated output may not always meet specific expectations regarding complex parameters.

If a function uses a custom object (like a Config class) as an argument, the automatic converter may describe it simply as a generic "object" without detailing its internal properties.

In these cases, manually defining the JSON schema is preferred to ensure nested properties (such as theme or font_size within a config object) are explicitly defined for the model.

    import json
    from transformers.utils import get_json_schema

    class Config:
        def __init__(self):
            self.theme = "light"
            self.font_size = 14

    def update_config(config: Config):
        """
        Updates the configuration of the system.

        Args:
            config: A Config object

        Returns:
            True if the configuration was successfully updated, False otherwise.
        """

    update_config_schema = {
        "type": "function",
        "function": {
            "name": "update_config",
            "description": "Updates the configuration of the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "config": {
                        "type": "object",
                        "description": "A Config object",
                        "properties": {"theme": {"type": "string"}, "font_size": {"type": "number"} },
                        },
                    },
                "required": ["config"],
                },
            },
        }

    print(f"--- [Automatic] ---")
    print(json.dumps(get_json_schema(update_config), indent=2))

    print(f"\n--- [Manual Schemas] ---")
    print(json.dumps(update_config_schema, indent=2))

```
--- [Automatic] ---
{
  "type": "function",
  "function": {
    "name": "update_config",
    "description": "Updates the configuration of the system.",
    "parameters": {
      "type": "object",
      "properties": {
        "config": {
          "type": "object",
          "description": "A Config object"
        }
      },
      "required": [
        "config"
      ]
    }
  }
}

--- [Manual Schemas] ---
{
  "type": "function",
  "function": {
    "name": "update_config",
    "description": "Updates the configuration of the system.",
    "parameters": {
      "type": "object",
      "properties": {
        "config": {
          "type": "object",
          "description": "A Config object",
          "properties": {
            "theme": {
              "type": "string"
            },
            "font_size": {
              "type": "number"
            }
          }
        }
      },
      "required": [
        "config"
      ]
    }
  }
}
```

## Summary and next steps

Now you understand function calling with FunctionGemma. Key takeaways from this include:

- **Defining Tools**: You can define tools using two methods: creating a manual JSON schema or passing raw Python functions, where the system parses type hints and docstrings.
- **Schema Caveats**: While automatic conversion works for simple types, it struggles with complex custom objects. In these cases, manual JSON schema definition is required to ensure nested properties are visible to the model.

Check out the following docs next:

- [Full function calling sequence with FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/full-function-calling-sequence-with-functiongemma)
- [Fine-tuning with FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma)



|---|---|---|---|---|
| [![](https://ai.google.dev/static/site-assets/images/docs/notebook-site-button.png)View on ai.google.dev](https://ai.google.dev/gemma/docs/functiongemma/full-function-calling-sequence-with-functiongemma) | [![](https://www.tensorflow.org/images/colab_logo_32px.png)Run in Google Colab](https://colab.research.google.com/github/google-gemini/gemma-cookbook/blob/main/docs/functiongemma/full-function-calling-sequence-with-functiongemma.ipynb) | [![](https://www.kaggle.com/static/images/logos/kaggle-logo-transparent-300.png)Run in Kaggle](https://kaggle.com/kernels/welcome?src=https://github.com/google-gemini/gemma-cookbook/blob/main/docs/functiongemma/full-function-calling-sequence-with-functiongemma.ipynb) | [![](https://ai.google.dev/images/cloud-icon.svg)Open in Vertex AI](https://console.cloud.google.com/vertex-ai/colab/import/https%3A%2F%2Fraw.githubusercontent.com%2Fgoogle-gemini%2Fgemma-cookbook%2Fmain%2Fdocs%2Ffunctiongemma%2Ffull-function-calling-sequence-with-functiongemma.ipynb) | [![](https://www.tensorflow.org/images/GitHub-Mark-32px.png)View source on GitHub](https://github.com/google-gemini/gemma-cookbook/blob/main/docs/functiongemma/full-function-calling-sequence-with-functiongemma.ipynb) |

FunctionGemma is a specialized version of the Gemma 3 270M model, trained specifically for function calling improvements. It has the same architecture as Gemma, but uses a different chat format and tokenizer.

This guide shows the complete workflow for using FunctionGemma within the Hugging Face ecosystem. It covers the essential setup steps, including installing necessary Python packages like `torch` and `transformers`, and loading the model via the Hugging Face Hub. The core of the tutorial demonstrates a three-stage cycle for connecting the model to external tools: the **Model's Turn** to generate function call objects, the **Developer's Turn** to parse and execute code (such as a weather API), and the **Final Response** where the model uses the tool's output to answer the user.

## Setup

Before starting this tutorial, complete the following steps:

- Get access to FunctionGemma by logging into [Hugging Face](https://huggingface.co/google/functiongemma-270m-it) and selecting **Acknowledge license** for a FunctionGemma model.
- Generate a Hugging Face [Access Token](https://huggingface.co/docs/hub/en/security-tokens#how-to-manage-user-access-token) and add it to your Colab environment.

This notebook will run on either CPU or GPU.

## Install Python packages

Install the Hugging Face libraries required for running the FunctionGemma model and making requests.

    # Install PyTorch & other libraries
    pip install torch

    # Install the transformers library
    pip install transformers

After you have accepted the license, you need a valid Hugging Face Token to access the model.

    # Login into Hugging Face Hub
    from huggingface_hub import login
    login()

## Load Model

Use the `torch` and `transformers` libraries to create an instance of a `processor` and `model` using the `AutoProcessor` and `AutoModelForCausalLM` classes as shown in the following code example:

    from transformers import AutoProcessor, AutoModelForCausalLM

    GEMMA_MODEL_ID = "google/functiongemma-270m-it"

    processor = AutoProcessor.from_pretrained(GEMMA_MODEL_ID, device_map="auto")
    model = AutoModelForCausalLM.from_pretrained(GEMMA_MODEL_ID, dtype="auto", device_map="auto")

## Example Use Cases

Function calling connects the generative capabilities of Gemma and the external data and services. Here are some common applications:

- **Answering Questions with Real-Time Data:** Use a search engine or weather API to answer questions like "What's the weather in Tokyo?" or "Who won the latest F1 race?"
- **Controlling External Systems:** Connect Gemma to other applications to perform actions, such as sending emails ("Send a reminder to the team about the meeting"), managing a calendar, or controlling smart home devices.
- **Creating Complex Workflows**: Chain multiple tool calls together to accomplish multi-step tasks, like planning a trip by finding flights, booking a hotel, and creating a calendar event.

## Using Tools

The core of function calling involves a four-step process:

1. **Define Tools**: Create the functions your model can use, specifying arguments and descriptions (e.g., a weather lookup function).
2. **Model's Turn**: FunctionGemma receives the user's prompt and a list of available tools. It generates a special object indicating which function to call and with what arguments instead of a plain text response.
3. **Developer's Turn**: Your code receives this object, executes the specified function with the provided arguments, and formats the result to be sent back to the model.
4. **Final Response**: FunctionGemma uses the function's output to generate a final, user-facing response.

Let's simulate this process.

    # Define a function that our model can use.
    def get_current_weather(location: str, unit: str = "celsius"):
        """
        Gets the current weather in a given location.

        Args:
            location: The city and state, e.g. "San Francisco, CA" or "Tokyo, JP"
            unit: The unit to return the temperature in. (choices: ["celsius", "fahrenheit"])

        Returns:
            temperature: The current temperature in the given location
            weather: The current weather in the given location
        """
        return {"temperature": 15, "weather": "sunny"}

### Model's Turn

Here's the user prompt `"Hey, what's the weather in Tokyo right now?"`, and the tool `[get_current_weather]`. FunctionGemma generates a function call object as follows.

    prompt = "Hey, what's the weather in Tokyo right now?"
    tools = [get_current_weather]

    message = [
            # ESSENTIAL SYSTEM PROMPT:
            # This line activates the model's function calling logic.
            {"role": "developer", "content": "You are a model that can do function calling with the following functions"},
            {"role": "user", "content": prompt},
    ]

    inputs = processor.apply_chat_template(message, tools=tools, add_generation_prompt=True, return_dict=True, return_tensors="pt")
    output = processor.decode(inputs["input_ids"][0], skip_special_tokens=False)

    out = model.generate(**inputs.to(model.device), pad_token_id=processor.eos_token_id, max_new_tokens=128)
    generated_tokens = out[0][len(inputs["input_ids"][0]):]
    output = processor.decode(generated_tokens, skip_special_tokens=True)

    print(f"Prompt: {prompt}")
    print(f"Tools: {tools}")
    print(f"Output: {output}")

```
Prompt: Hey, what's the weather in Tokyo right now?
Tools: [<function get_current_weather at 0x79b7e0f52e80>]
Output: <start_function_call>call:get_current_weather{location:<escape>Tokyo, Japan<escape>}<end_function_call>
```
>
> > [!NOTE]
> > **Note:** To ensure FunctionGemma correctly interprets the available tools and generates a structured call instead of plain text, the **developer** message is essential. This specific system prompt instructs the model that it has permission and capability to perform function calling.
>
    message = [
            # ESSENTIAL SYSTEM PROMPT:
            # This line activates the model's function calling logic.
            {"role": "developer", "content": "You are a model that can do function calling with the following functions"},
            {"role": "user", "content": prompt},
    ]

### Developer's Turn

Your application should parse the model's response to extract function name and argments, and append function call result with the `tool` role.
>
> > [!NOTE]
> > **Note:** Always validate function names and arguments before execution.
>
    import re

    def extract_tool_calls(text):
        def cast(v):
            try: return int(v)
            except:
                try: return float(v)
                except: return {'true': True, 'false': False}.get(v.lower(), v.strip("'\""))

        return [{
            "name": name,
            "arguments": {
                k: cast((v1 or v2).strip())
                for k, v1, v2 in re.findall(r"(\w+):(?:<escape>(.*?)<escape>|([^,}]*))", args)
            }
        } for name, args in re.findall(r"<start_function_call>call:(\w+)\{(.*?)\}<end_function_call>", text, re.DOTALL)]

    calls = extract_tool_calls(output)
    if calls:
        message.append({
            "role": "assistant",
            "tool_calls": [{"type": "function", "function": call} for call in calls]
        })
        print(message[-1])

        # Call the function and get the result
        #####################################
        # WARNING: This is a demonstration. #
        #####################################
        # Using globals() to call functions dynamically can be dangerous in
        # production. In a real application, you should implement a secure way to
        # map function names to actual function calls, such as a predefined
        # dictionary of allowed tools and their implementations.
        results = [
            {"name": c['name'], "response": globals()[c['name']](**c['arguments'])}
            for c in calls
        ]

        message.append({
            "role": "tool",
            "content": results
        })
        print(message[-1])

```
{'role': 'assistant', 'tool_calls': [{'type': 'function', 'function': {'name': 'get_current_weather', 'arguments': {'location': 'Tokyo, Japan'} } }]}
{'role': 'tool', 'content': [{'name': 'get_current_weather', 'response': {'temperature': 15, 'weather': 'sunny'} }]}
```
>
> > [!NOTE]
> > **Note:** For optimal results, append the tool execution result to your message history using the specific format below. This ensures the chat template correctly generates the required token structure (e.g., `response:get_current_weather{temperature:15,weather:<escape>sunny<escape>}`).
>
    message.append({
        "role": "tool",
        "content": {
            "name": function_name,
            "response": function_response
        }
    })

In case of multiple independent requests:

    message.append({
        "role": "tool",
        "content": [
            {
                "name": function_name_1,
                "response": function_response_1
            },
            {
                "name": function_name_2,
                "response": function_response_2
            }
        ]
    })

### Final Response

Finally, FunctionGemma reads the tool response and reply to the user.

    inputs = processor.apply_chat_template(message, tools=tools, add_generation_prompt=True, return_dict=True, return_tensors="pt")
    out = model.generate(**inputs.to(model.device), pad_token_id=processor.eos_token_id, max_new_tokens=128)
    generated_tokens = out[0][len(inputs["input_ids"][0]):]
    output = processor.decode(generated_tokens, skip_special_tokens=True)
    print(f"Output: {output}")
    message.append({"role": "assistant", "content": output})

```
Output: The current weather in Tokyo is sunny with a temperature of 15 degrees Celsius.
```

You can see the full chat history below.

    # full history
    for item in message:
      print(item)

    print("-"*80)
    output = processor.decode(out[0], skip_special_tokens=False)
    print(f"Output: {output}")

```
{'role': 'developer', 'content': 'You are a model that can do function calling with the following functions'}
{'role': 'user', 'content': "Hey, what's the weather in Tokyo right now?"}
{'role': 'assistant', 'tool_calls': [{'type': 'function', 'function': {'name': 'get_current_weather', 'arguments': {'location': 'Tokyo, Japan'} } }]}
{'role': 'tool', 'content': [{'name': 'get_current_weather', 'response': {'temperature': 15, 'weather': 'sunny'} }]}
{'role': 'assistant', 'content': 'The current weather in Tokyo is sunny with a temperature of 15 degrees Celsius.'}
---
Output: <bos><start_of_turn>developer
You are a model that can do function calling with the following functions<start_function_declaration>declaration:get_current_weather{description:<escape>Gets the current weather in a given location.<escape>,parameters:{properties:{location:{description:<escape>The city and state, e.g. "San Francisco, CA" or "Tokyo, JP"<escape>,type:<escape>STRING<escape>},unit:{description:<escape>The unit to return the temperature in.<escape>,enum:[<escape>celsius<escape>,<escape>fahrenheit<escape>],type:<escape>STRING<escape>} },required:[<escape>location<escape>],type:<escape>OBJECT<escape>} }<end_function_declaration><end_of_turn>
<start_of_turn>user
Hey, what's the weather in Tokyo right now?<end_of_turn>
<start_of_turn>model
<start_function_call>call:get_current_weather{location:<escape>Tokyo, Japan<escape>}<end_function_call><start_function_response>response:get_current_weather{temperature:15,weather:<escape>sunny<escape>}<end_function_response>The current weather in Tokyo is sunny with a temperature of 15 degrees Celsius.<end_of_turn>
```

## Summary and next steps

You have established how to build an application that can calls functions with FunctionGemma. The workflow is established through a four-stage cycle:

1. **Define Tools**: Create the functions your model can use, specifying arguments and descriptions (e.g., a weather lookup function).
2. **Model's Turn**: The model receives the user's prompt and a list of available tools, returning a structured function call object instead of plain text.
3. **Developer's Turn**: The developer parses this output using regular expressions to extract function names and arguments, executes the actual Python code, and appends the results to the chat history using the specific tool role.
4. **Final Response**: The model processes the tool's execution result to generate a final, natural language answer for the user.

Check out the following documentation for further reading.

- [Fine-tuning with FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma)





query_prompt = """Generate a concise,focused search query based on the user's question and what we've learned from previous searches (if any). Try to structure your query to match what we would find in the actual text.
    E.g. if the user asks "What is the company's revenue?", a good query might be "company revenue" or "company revenue 2024" or "company revenue 2024 Q1"


    Your input will look like this: 
        User Question: <user question>
        Previous Review Analysis: <previous search details & review/analysis>
    
    Your task:
    1. Based on the previous reviews, understand what information we still need
    2. Consider the question, determine what category or categories the information belongs to based on the category guidance
    3. Generate a targeted search query and a filterto find the missing information

    ###Output Format###

    1. search_query: The generated search query
    2. filter: The filter to use with the search query (Azure AI Search OData syntax)

    ###Category Guidance###

    
    {
    "CategoryName": "Proposal Boilerplate",
    "Description": "This category includes general company information, capabilities, and standard content used in proposals",
    "SampleQuestions": [
        "Why choose DXC?",
        "Can you provide a brief overview of DXC Technology?",
        "What is the history and background of DXC Technology?",
        "What are the key industries and sectors DXC serves?",
        "What are the primary services and solutions offered by DXC Technology?",
        "How does DXC support digital transformation for its clients?",
        "Can you describe DXC's approach to cloud and platform services?"
    ]
    },
    "CategoryName": "Playbook",
    "Description": "This category includes strategic guidance and methodologies for consulting and technical practices",
    "SampleQuestions": [
        "What is DXC's consulting methodology?",
        "What is DXC's approach to Data & AI?"
    ]
    },
    "CategoryName": "Brochure",
    "Description": "This category includes product and service offering overviews",
    "SampleQuestions": [
        "What are DXC's network offerings?",
        "What products does DXC offer?",
        "What are DXC's service capabilities?"
    ]
    },

    "CategoryName": "Customer Presentation",
    "Description": "This category includes customer-facing presentation materials about specific products or services",
    "SampleQuestions": [
        "What innovative AI projects has DXC completed?"
    ]
    }

    
    ###Example###
    
    User Question: "What are the key regions where DXC operates?"
    Assistant: 
    search_query: "dxc operating regions"
    filter: "category eq 'Proposal Boilerplate'"

    """
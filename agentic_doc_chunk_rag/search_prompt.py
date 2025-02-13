
query_prompt = """Generate a search query based on the user's question and what we've learned from previous searches (if any). Your search query should be a paragraph of what you think you will find in the documents themselves.


    Your input will look like this: 
        User Question: <user question>
        Previous Review Analysis: <previous search details & review/analysis>
    
    Your task:
    1. Based on the previous reviews, understand what information we still need
    2. Consider the question, determine what category or categories the information belongs to based on the category guidance
    3. Generate a paragraph of what you think you will find in the documents themselves

    ###Output Format###

    1. search_query: The generated search query
    2. filter: The filter to use with the search query (Azure AI Search OData syntax)

    ###Category Guidance###

    
    {
    "CategoryName": "home",
    "Description": "This category includes general questions about Dan's house, 337 Goldman Drive",
    "SampleQuestions": [
        "What year was my house built?",
        "What are the top 3 most important items from my home inspection?"
    ]
    },
    "CategoryName": "health",
    "Description": "This category includes questions about Dan's health",
    "SampleQuestions": [
        "What were my latest lab results"
    ]
    },
    "CategoryName": "finance",
    "Description": "This category includes questions about Dan's finances",
    "SampleQuestions": [
        "What were my taxes in 2022?",
        "How much mortgage interest did i pay last year?"
    ]
    }

    
    ###Example###
    
    User Question: "What year was my house built?"
    Assistant: 
    search_query: "the house was built in 2019"
    filter: "category eq 'home'"

    User Question: "How much mortgage interest did i pay last year?"
    Assistant: 
    search_query: " 1 Mortgage interest received from payer(s)/borrower(s)*
      $1,000
 Outstanding mortgage principal 
$10,000
 Refund of overpaid interest 
$0.00
 Mortgage origination date 
11/29/2022
 Mortgage insurance premiums 
$100"
    filter: "category eq 'finance'"

    """
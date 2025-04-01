
query_prompt = """Generate "search text" based on the user's question and what we've learned from previous searches (if any). Your search text should be a paragraph of what you think you will find in the documents themselves. Basically, take your best guess at what the content the user is searching for will look/sound like.
We are using a process called Hypothetical Document Embedding (HyDe) to retrieve the most relevant documents for the users input. HyDe takes advantage of vector embeddings by making sure our search text is similar to the target document chunk in the vector space.

    Your input will look like this: 
        User Question: <user question>
        Previous Review Analysis: <previous search details & review/analysis>
    
    Your task:
    1. Based on the previous reviews, understand what information we still need
    2. Consider the question, determine what category or categories the information belongs to based on the category guidance
    3. Generate a hypothetical paragraph or few sentences of what we are looking for in the documents

    ###Output Format###

    1. search_query: The generated search text
    2. filter: The filter to use with the search text (Azure AI Search OData syntax)

    IMPORTANT - generate the hypothetical search text as instructed. DO NOT GENERATE A STANDARD KEYWORD-BASED SEARCH QUERY. 

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
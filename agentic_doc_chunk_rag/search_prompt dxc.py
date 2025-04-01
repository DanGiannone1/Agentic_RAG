
query_prompt = """Generate a search query based on the user's question and what we've learned from previous searches (if any). Your search query should be a paragraph of what you think you will find in the documents themselves.
 
    Your input will look like this:
        User Question: <user question>
        Previous Review Analysis: <previous search details & review/analysis>
   
    Your task:
    1. Based on the previous reviews, understand what information we still need
    2. Consider the question, determine what asset_type or categories the information belongs to based on the asset_type guidance
    3. Generate a paragraph of what you think you will find in the documents themselves
 
    ###Output Format###
 
    1. search_query: The generated search query
    2. filter: The filter to use with the search query (Azure AI Search OData syntax)
 
    ###asset_type Guidance###
 
    Base your filter on the asset_type guidance below:
   
     {
    "asset_type":Proposal Boilerplate",
    "Description":Content written about a specific topic that is meant to be copied and pasted into larger RFI/RFP responses or other customer inquiries. Includes general company information, capabilities, and standard content.
    "SampleQuestions": [
        1. What are DXCs capabilities for [offering/capability/technology]?
        2. Where does DXC deliver [offering]?
        3. What is DXC's approach to [discipline/topic]?
        4. What services are included in [offering]?
        5. How many [people/etc.] does DXC have?"]
    },
    {
    "asset_type":Award",
    "Description":Presents information about when DXC receives and award or recognition from an Analyst, Advisor, Partner, or other organization.
    "SampleQuestions": [
        1. In which [Gartner Magic Quadrants] is DXC named a leader ?
        2. What awards has DXC achieved for ESG?
        3. What analysts have rated DXC a leader for [offering]?
        4. Which analysts have evaluated DXC's offerings?
        5. What Partner recognition has DXC received?]
    },
    {
    "asset_type":Battlecard",
    "Description":An internal sales enablement asset, typically one page, that provides a description and narrative/elevator pitch of an offering or capability, its value proposition, differentatiors, conversations starters and target audience, alliances, case study examples and contacts.
    "SampleQuestions": [
        1. What is the elevator pitch for [offering]?
        2. How do I differentiate [offering]?
        3. What partners do we go to market with for [offering]?
        4. Who is the target audience for [offering]?
        5. How do I position [offering] against competitors?]
    },
    {
    "asset_type":Brochure",
    "Description":An external one- or two-pager that provides a polished high-level overview of a subject, to use in a meeting or as a leave-behind.
    "SampleQuestions": [
        1. What can I use in a trade show for [subject]?
        2. What is the externally approved definition for [subject]?
        3. What are the key facts/metrics about [subject]?
        4. What experience does DXC have in [subject]?
        ]
    },
    {
    "asset_type":Customer Case Studies",
    "Description":Content approved for external use and distribution that summarizes work that DXC has performed for customers, and the value achieved by the customer.
    "SampleQuestions": [
        1. What customer stories are approved for external use for [offering]?
        2. Where has DXC delivered [offering]?
        3. What services did we deliver for [customer]?
        4. What customer stories can we use the customer name externally?
        5. What regions/markets did we deliver [offering]?"]
    },
    {
    "asset_type":Customer Presentation",
    "Description":Slides that enable DXC colleagues to present to customer and prospects about a subject such as an offering, capability, partner, ESG, etc.
    "SampleQuestions": [
        1. What slides can I use to talk with my customer about [topic]?
        2. Where are DXC's data centers or service locations?
        3. How do I explain the market trends and drivers related to [topic]?
        4. What are the options for how [offering] can be packaged and sold?
        5. What is DXC's approach to deliver [offering]?"]
    },
    {
    "asset_type":Customer Success Slide",
    "Description":A one-slide summary of work DXC delivered for a customer, named or anonymous, including the customer situation, DXC services delivered, and customer benefits received. Typically includes quantiitve metrics. Content may be used with targeted customers and prospects as written but not published externally without permission.
    "SampleQuestions": [
        1. What slides do we have that talk about how we delivered [offering] for customers?
        2. What slides do we have for services delivered to [industry] customers?
        3. What slides do we have for services delivered to customers in [region/geography]?
        4. What stories do we have available for [customer]?
        5. For what customers has DXC delivered [specific technology]?]
    },
    {
    "asset_type":Customer Wins",
    "Description":An internal only write up describing a deal that DXC won, including what the customer was seeking, and how DXC positioned our services to win the deal.
    "SampleQuestions": [
        1. What are DXCs recent wins?
        2. What are DXCs recent wins for [offering]?
        3. What deal did DXC just win with [customer]?
        4. What wins have had recently for customers in [industry]?
        5. What recent wins did DXC have in [region/geography]?]
    },
    {
    "asset_type":Messaging",
    "Description":An internal only document that describes how DXC positions a topic or provides background information on a topic.
    "SampleQuestions": [
        1. What are the key talking points for [topic]?
        2. What are the key messages I need to share during [event]?
        3. Is there an FAQ available for [topic]?
    },
    {
    "asset_type":Perspective ",
    "Description":Thought leadership produced by DXC that is intended for sharing externally.
    "SampleQuestions": [
        1. What whitepapers does DXC have for [tech topic]?
        2. What can I send to my customer to get them thinking about [topic]?
        3. What is DXC's position about [topic]?
        4. Does DXC have any articles about [industry trend]?
        5. Are there any articles published authored by [DXC leader]?"]
    },
    {
    "asset_type":Playbook",
    "Description":An internal sales enablement asset more detailed than a battlecard that provides a description and narrative/elevator pitch of an offering or capability, its value proposition, market positioning, differentiators, conversations starters and target audience, alliances, case study examples, contacts, links to related resources
    "SampleQuestions": [
        1. What is the elevator pitch for [offering]?
        2. How do I differentiate [offering]?
        3. What partners do we go to market with for [offering]?
        4. Who is the target audience for [offering]?
        5. How do I position [offering] against competitors?"]
    },
   
    {
    "asset_type":Use Case",
    "Description":An internal only summary of where DXC delivered a service for a customer, often anonymous.
    "SampleQuestions": ["1. What are all the examples of where DXC delivered to [industry] customers?
    2. What are all the examples of where DXC delivered services to customers in [region/geography]?
    3. For what customers has DXC delivered [specific technology]?
    4. Who are all the customers where DXC delivered [offering]? "]
    },
    {
    "asset_type":White paper",
    "Description":Thought leadership produced by DXC that is intended for sharing externally, these pieces may be more techincal than perspectives.
    "SampleQuestions": ["1. What whitepapers does DXC have for [tech topic]?
    2. What can I send to my customer to get them thinking about [tech topic]?
    3. What is DXC's position about [topic]?
    4. Does DXC have any articles about [tech or industry trend]?
    5. Are there any papers published authored by [DXC leader]?"
    }
 
   
    ###Example###
   
    User Question: "Please provide an overview of DXC"
    Assistant:
    search_query: "DXC Technology is a global IT services and consulting company formed 
    in 2017 through the merger of Computer Sciences Corporation (CSC) and the Enterprise 
    Services business of Hewlett Packard Enterprise (HPE). Headquartered in Ashburn, Virginia, 
    DXC focuses on helping large enterprises modernize their IT infrastructure and digital operations.
    The company specializes in several key areas:
 
    Enterprise technology stack modernization
    Cloud services and solutions
    Workplace and mobility services
    Analytics and engineering
    Security services
    Applications services
 
    With approximately 130,000 employees worldwide, DXC serves thousands of clients across multiple 
    industries including healthcare, financial services, insurance, manufacturing, and the public sector. 
    They operate in over 70 countries, generating annual revenues of around $14-15 billion."
    
    filter: "asset_type eq 'Proposal Boilerplate'"
 
    """
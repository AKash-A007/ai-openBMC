Server logs  are difficult to analyse manullay 

solution= AI powered diagonostic for OpenBMC


Its week 3 completed . 
ingestion completed
parsing completed
RAG completed
LLM -- prompt + reasoning + diagonise complete 
main pipeline file also created 

THIS WAS MY STICKY NOTES 
"""
TODO 

create week 2 rag function 
- input should be "Memory ECC error"
-output   "Repeated ECC errors often indicate DIMM degradation."
 [ after retreving the best chunk form chromaDB split it into sentences and use cosine similarity to pick the single sentence most relevant to the query]

Agent should only ask search_knowledge() but should never know how chromaDB works and the ingestions - good software design 

build  prompt template - LLMS needs instructions prompt engineering is essentially API design for AI.

create diagnosis agent 
def diagnose (event)
input - event+retrieved content
output -root cause + severity + confidence +recommendation

connect everthing together in a file 
""""
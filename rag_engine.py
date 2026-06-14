#first step is to create embeddings 
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path
#knowledge base
#preparing the knowledge base, we will read all the text files in the knowledge folder and create 
# embeddings for them
knowledge_base_path = Path("./knowledge")
documnets = []
ids = []
# for file in knowledge_base_path.glob("*.txt"):

#     if file.is_file():
#         content = file.read_text(encoding="utf-8",errors="ignore")
#         documnets.append(content)
#         ids.append(file.stem)

"""
    This is the basic apporch but for this project its better to use chunking approch
    so that it will return the exact section of the document that is relevant to the query, instead of 
    returning the whole document.
    The chunking approch will be implemented in the next step.
"""

all_chunks = []
all_ids = []
metadatas =[]

def chunk_text(text, chunk_size=500, overlap=50):
    """
    This function will take a text and chunk it into smaller chunks of size chunk_size with an 
    overlap of overlap
    The overlap is used to make sure that the chunks are not disjoint and the context is preserved. 
    The overlap is the number of characters that will be repeated in the next chunk.
    For example, if the chunk size is 500 and the overlap is 50, then the first chunk will be 
    from 0 to 500, the second chunk will be from 450 to 950   
    """
    chunks = []
    start = 0
    while start < len(text):
        #to calculate the end index of the chunk, we will take the minimum of the start index + chunk size and
        #  the length of the text
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        #addressing the overlap, we will move the start index by chunk size - overlap, so that the 
        # next chunk will start from the end of the previous chunk - overlap
        start += chunk_size - overlap
    return chunks


for file in knowledge_base_path.glob("*.txt"):
    text = file.read_text(encoding="utf-8",errors="ignore")
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    for idx, chunk in enumerate(chunks):
        all_chunks.append(chunk)
        all_ids.append(f"{file.stem}_{idx}")
        metadatas.append({"source": file.stem, "chunk_index": idx})
model = SentenceTransformer('all-MiniLM-L6-v2')
#if no documents found in the knowledge folder, raise an error
if not all_chunks:
    raise ValueError("No documents found in knowledge folder")
#use batching if we have a large number of documents, this will speed up the embedding process 
# and also reduce the memory usage
embeddings = model.encode(
    all_chunks,
    batch_size=32,
    show_progress_bar=True
).tolist()

#chromadb is a vector database that can be used to store and query embeddings
#its like the google search for my documents, it will return the most relevant documents based on the query
client = chromadb.PersistentClient(
    path="./chroma_db"
)
collection = client.get_or_create_collection(name="openbmc_docs")
try:
    collection.add(
        
        documents=all_chunks,
        embeddings=embeddings,
        ids=all_ids,
        metadatas=metadatas
    )
except Exception as e:
    print(f"Error adding documents to collection: {e}")
results = collection.query(
    query_texts=["memory ECC error"],
    n_results=2
)
for doc, meta in zip(
    results["documents"][0],
    results["metadatas"][0]
):
    if meta:
        print(f"Source: {meta['source']}")
    else:
        print("Source: Unknown")

    print(doc)

import os
import tempfile
from time import sleep
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import streamlit as st
from langchain_core.documents import Document
from pypdf import PdfReader


load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)

if "vector_db" not in st.session_state:
  st.session_state.vector_db = None

if "messages" not in st.session_state:
  st.session_state.messages = []

if "document_uploaded" not in st.session_state:
  st.session_state.document_uploaded = False


def process_file(uploaded_files):
  INDEX_PATH = "faiss_index"
  all_docs = []  # Collect pages from ALL files

  for uploaded_file in uploaded_files:
    reader = PdfReader(uploaded_file)
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            all_docs.append(
                Document(
                    page_content=text,
                    metadata={"source": uploaded_file.name, "page": page_num},
                )
            )


  embeddings = HuggingFaceEmbeddings(
      model_name="sentence-transformers/all-MiniLM-L6-v2"
  )
  splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
  chunks = splitter.split_documents(all_docs)

  vector_db = FAISS.from_documents(documents=chunks, embedding=embeddings)
  vector_db.save_local(INDEX_PATH)

  st.session_state.vector_db = vector_db


st.subheader("Q&A Chatbot - Ask Questions")

if not st.session_state.document_uploaded:
  files = st.file_uploader(
      label="Select your pdf files", type="pdf", accept_multiple_files=True
  )

  # Only process after user uploads at least one file
  if files:
    with st.spinner("Processing..."):
      process_file(files)

    st.success("Files processed successfully")
    st.session_state.document_uploaded = True
    sleep(2)
    st.rerun()

if st.session_state.document_uploaded and st.session_state.vector_db:
  query = st.chat_input("Ask anything...")
  for oneMsg in st.session_state.messages:
    st.chat_message(oneMsg["role"]).markdown(oneMsg["content"])

  if query:
    st.session_state.messages.append({"role": "user", "content": query})
    st.chat_message("user").markdown(query)
    matching_docs = st.session_state.vector_db.similarity_search(query, k=4)

    context = "\n\n".join(doc.page_content for doc in matching_docs)

    prompt = f"""You are a helpful assistant. Answer the query based only on the given context.
        If the query is greetings, greet them in return and ask how you can help them.
        If the answer is not in the context, say "I don't have enough information in the provided documents."
        
        Context:
        {context}

        Query: {query}
        """
    result = llm.invoke(prompt)
    st.chat_message("ai").markdown(result.content)
    st.session_state.messages.append({"role": "ai", "content": result.content})

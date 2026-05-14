from graph_retriever import get_graph_answer_context

query = "Why is Payment API failing?"

result = get_graph_answer_context(query)

print("User Query:")
print(query)

print("\nGraph Context:")
print(result)
"""
@author: Rohini
created: 2024-04-27
@github: @arohini

"""

from pymongo.mongo_client import MongoClient
from pymongo.operations import SearchIndexModel
from load_dotenv import load_dotenv
import os
import time
import sys

load_dotenv()

def create_atlas_vector_index(database_name: str, collection_name: str, \
                              index_name: str, custom_field: dict) -> None:
    """
    This is a function that creates a vector search index in MongoDB Atlas 
    for a specified collection. It connects to the MongoDB Atlas cluster using 
    the provided connection URI, accesses the specified database and collection, 
    and then creates a search index with the given name and path for vector data. 
    The function also includes error handling for connection and index creation 
    issues, and it polls until the index is ready for querying.

    Args:
        database_name (str): The name of the database
        collection_name (str): The name of the collection
        index_name (str): The name of the search index
        custom_field (dict): The custom field definition for the vector index
    """
    
    client = None
    try:
      # Create a MongoDB client using the connection URI
      client = MongoClient(os.getenv("atlas_mongodb_uri"))
    
    except Exception as e:
      print("Error connecting to MongoDB: " + str(e))
      return
    
    if client:
      # Access your database and collection
      database = client[database_name]
      collection = database[collection_name]

      # Create your index model, then create the search index
      search_index_model = SearchIndexModel(
        definition={
          "fields": [custom_field]
        },
        name=index_name, # name of the search index
        type="vectorSearch"
      )
      try:
        result = collection.create_search_index(model=search_index_model)
        print("New search index named " + result + " is building.")
      except Exception as e:
        print("Error creating search index: " + str(e))
        return sys.exit(1)

    # Wait for initial sync to complete
      print("Polling to check if the index is ready. This may take up to a minute.")
      predicate=None
      if predicate is None:
        predicate = lambda index: index.get("queryable") is True

      while True:
        indices = list(collection.list_search_indexes(result))
        if len(indices) and predicate(indices[0]):
          break
        time.sleep(5)
      print(result + " is ready for querying.")
      client.close()
      return result
    
    
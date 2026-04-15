import numpy as np
# Scale: 0 to 1 [Action, Sci-Fi, Romance, Comedy]
user_profile = np.array([0.9, 1.0, 0.1, 0.4])

# 2. Movie features (The "Item Matrix")
# Each movie is also represented as a vector of the same 4 categories.
movies = {
    "Interstellar": np.array([0.8, 1.0, 0.2, 0.1]),
    "The Notebook":  np.array([0.1, 0.1, 1.0, 0.5]),
    "Deadpool":      np.array([0.9, 0.3, 0.4, 0.9])
}

# 3. The Calculation (Dot Product)
# This linear algebra operation calculates how well the user profile "aligns" with each movie.
for title, features in movies.items():
    score = np.dot(user_profile, features)
    print(f"Recommendation Score for '{title}': {score:.2f}")

# Output:
# Interstellar: 1.78 (Highest score - Recommend this!)
# Deadpool: 1.51
# The Notebook: 0.49 (Lowest score)
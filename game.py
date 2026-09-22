board = [
    "APPLE",
    "MOON",
    "COURT",
    "TURKEY",
    "PIZZA",
    "BAT",
    "RAIN",
    "PARIS",
    "GLASS",
    "BASKETBALL",
    "ROSE",
    "SHARK",
    "DESERT",
    "PIANO",
    "TIGER",
    "DRAGON"
]

hidden_chain = [
    "SPORTS",
    "BASKETBALL",
    "COURT",
    "PARIS",
    "DRAGON"
]

current_position = 0
lives = 3

print("Welcome to CONNECTION!")
print()
print("Your board:")
for word in board:
    print(word)
print("Starting clue:", hidden_chain[0])
print("Lives:", lives)

while True:
    guess = input("Choose a word: ").upper()
    print("You chose:", guess)

    if guess == hidden_chain[current_position + 1]:
        print("Yes!")
        current_position += 1
        if current_position == len(hidden_chain) - 1:
            print("You got it! Game over.")
        else:
            print("Next clue:", hidden_chain[current_position])
    else:
        print("Wrong!")
        lives -= 1
        print("Lives: ", lives)
        if lives == 0:
            print("End game.")
            break
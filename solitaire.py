import random


class Deck:
    def __init__(self, deck = None):
        self.deck = deck or []
        self.open_cards = []

    def deal_to_tableau(self, tableau):
        if len(self.deck) < 7:
            print('Not enough cards in stock')
            return
        for i in range(7):
            card = self.deck.pop(0)
            tableau.rows[i].append({'card': card, 'open': True})
        print('Stock dealt to tableau.')    

    def place_from_waste(self, tableau, col_idx):
        if not self.open_cards:
            print('Waste is empty')
            return
        card = self.open_cards.pop()  
        tableau.rows[col_idx].append({'card': card, 'open': True})
        tableau.show()    

    def create_deck(self):
      self.deck = []
      rank = ['6','7','8', '9', '10', 'В', 'Д', 'К', 'Т']
      suit = ['♥', '♦', '♣', '♠']

      for i in suit:
        for j in rank:
          self.deck.append(i + j)

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def open_card(self):
        card = random.choice(self.deck) 
        self.open_cards.append(card)
        self.deck.remove(card)
                
          
class Tableau:

    def __init__(self, deck):
        self.rows = [[] for _ in range(7)]          
        self.deck = deck

    def create_tableau(self):
        
        for i in range(7):
            for _ in range(i + 1):
                card = self.deck.pop(0)
                self.rows[i].append({'card': card, 'open': False})

            self.rows[i][-1]['open'] = True     

    def show(self):

        if d.open_cards:
            print(f'= Waste: {d.open_cards[-1]} =')
        else:
            print('= Waste: empty =')
        print('~ ↓ Tableau ↓ ~')

        self.open_cards = []

        max_height = max(len(col) for col in self.rows)

        for level in range(max_height):
            for col in self.rows:
                if not col:
                        print('*', end=' ')
                        continue
                if level < len(col):
                    card = col[level]
                    
                    if card['open']:
                        print(f"{card['card']:>3}", end=' ')
                        self.open_cards.append(card['card'])
                    else:
                        print(' []', end=' ')
                else:
                    print('   ', end=' ')
            print()

    def is_same_suit_sequence(self, cards):
        suit = cards[0]['card'][0]
        for c in cards:
            if c['card'][0] != suit:
                return False
        return True

    def move_card(self, from_card, to_card=None):

        from_col = None
        from_idx = None

        for col in self.rows:
            for i, c in enumerate(col):
                if c['card'] == from_card and c['open']:
                    from_col = col
                    from_idx = i
                    break
            if from_col:
                break

        if from_col is None:
            print('Card not found or not open')
            return

        moving_cards = from_col[from_idx:]

        if not self.is_same_suit_sequence(moving_cards):
            print('In Spider you can move only same-suit sequence')
            return

        to_col = None
        for col in self.rows:
            if col and col[-1]['card'] == to_card and col[-1]['open']:
                to_col = col
                break

        if to_card is None:
            for col in self.rows:
                if not col:
                    to_col = col
                    break
            if to_col is None:
                print('No empty column available')
                return    
        else:
            for col in self.rows:
                if col and col[-1]['card'] == to_card and col[-1]['open']:
                    to_col = col
                    break
            if to_col is None:
                print('Invalid target column')
                return    

        del from_col[from_idx:]
        if from_col:
            from_col[-1]['open'] = True

        to_col.extend(moving_cards)

        self.show()
            
RANK_ORDER = {
    '6': 0,
    '7': 1,
    '8': 2,
    '9': 3,
    '10': 4,
    'В': 5,
    'Д': 6,
    'К': 7,
    'Т': 8
}


class Game:
    
    def __init__(self, tableau):
        self.tableau = tableau       

    def parse_card(self, card):
        suit = card[0]
        rank = card[1:]
        return rank, suit

    def can_place(self, from_card, to_card):
        from_rank, from_suit = self.parse_card(from_card)
        to_rank, to_suit = self.parse_card(to_card)

        return RANK_ORDER[from_rank] + 1 == RANK_ORDER[to_rank] 
    
    def user_play(self):
        self.tableau.show()

        from_card = input('Which card to move (0 = deal from stock): ')

        if from_card == '0':
            d.deal_to_tableau(self.tableau)
            return

        if from_card in d.open_cards:
            col_idx = int(input('Put on which column (0-6): '))
            d.place_from_waste(self.tableau, col_idx)
            return

        if from_card not in self.tableau.open_cards:
            print('This card is not open')
            return

        to_card = input('Put on which card (ENTER = empty column): ')

        if to_card == '' or to_card == '*' or to_card == '**':
            self.tableau.move_card(from_card, to_card=None)
            print(f'{from_card} placed on empty column')
            return

        if to_card not in self.tableau.open_cards:
            print('This card is not open')
            return
        if self.can_place(from_card, to_card):
            self.tableau.move_card(from_card, to_card)
            print(f'{from_card} placed on {to_card}')
        else:
            print('Invalid move')


class Foundations:
    def __init__(self):
        self.foundations = {'♥': 0, '♦': 0, '♣': 0, '♠': 0}

    def is_full_sequence(self, col):

        if len(col) < 9:
            return False

        last_cards = col[-9:]
        suit = last_cards[0]['card'][0]

        for i, c in enumerate(last_cards):
            card_suit = c['card'][0]
            card_rank = c['card'][1:]

            if card_suit != suit:
                return False
            if RANK_ORDER[card_rank] != i:
                return False

        return True

    def collect_sequence(self, tableau):

        for idx, col in enumerate(tableau.rows):
            if self.is_full_sequence(col):
                suit = col[-9][0]['card'][0]  

                del col[-9:]
                self.foundations[suit] += 1
                print(f'Collected full sequence of {suit} in column {idx}!')

    def show(self):
        print('~ Foundations ~')
        for suit, count in self.foundations.items():
            print(f'{suit}: {count}')
        print("~~~~~~~~~~~~~~~~")


d = Deck()
d.create_deck()
d.shuffle_deck()

t = Tableau(d.deck)
t.create_tableau()

d.open_card()
g = Game(t)
f = Foundations()


while True:
    
    g.user_play()
    print(t.open_cards)
    f.collect_sequence(t) 
    f.show()

    if all(count >= 1 for count in f.foundations.values()):
        print("🎉 Game completed! 🎉")
        break

package api

import (
	"math/big"
	"slices"
	"strings"

	"github.com/jackc/pgx/v5/pgtype"

	"github.com/hsin19/finchie/services/backend/internal/db/dbq"
)

type tally struct {
	count  int
	amount pgtype.Numeric
}

func (t *tally) add(count int32, amount pgtype.Numeric) {
	t.count += int(count)
	t.amount = addNumeric(t.amount, amount)
}

// summarize folds the (kind, card) groups from TransactionTotals into the search total and the card
// facet, which skips the card filter: it keeps the groups that pass the kind filter.
func summarize(groups []dbq.TransactionTotalsRow) (tally, []CardTotal) {
	total := tally{amount: zero()}
	type cardKey struct{ institution, last4 string }
	cards := map[cardKey]*tally{}
	var cardOrder []cardKey

	for _, g := range groups {
		if g.KindMatch && g.CardMatch {
			total.add(g.RowCount, g.Amount)
		}
		if g.KindMatch {
			key := cardKey{institution: g.Institution}
			if g.CardLast4 != nil {
				key.last4 = *g.CardLast4
			}
			if cards[key] == nil {
				cards[key] = &tally{amount: zero()}
				cardOrder = append(cardOrder, key)
			}
			cards[key].add(g.RowCount, g.Amount)
		}
	}

	slices.SortFunc(cardOrder, func(a, b cardKey) int {
		if c := strings.Compare(a.institution, b.institution); c != 0 {
			return c
		}
		return strings.Compare(a.last4, b.last4)
	})
	byCard := make([]CardTotal, 0, len(cards))
	for _, key := range cardOrder {
		t := cards[key]
		card := CardTotal{Institution: key.institution, Count: t.count, Amount: decimalString(t.amount)}
		if key.last4 != "" {
			card.CardLast4 = &key.last4
		}
		byCard = append(byCard, card)
	}
	return total, byCard
}

// kindTotals is the kind facet, from KindTotals (already in kind order).
func kindTotals(rows []dbq.KindTotalsRow) []KindTotal {
	byKind := make([]KindTotal, 0, len(rows))
	for _, row := range rows {
		byKind = append(byKind, KindTotal{Kind: TransactionKind(row.Kind), Count: int(row.RowCount), Amount: decimalString(row.Amount)})
	}
	return byKind
}

func zero() pgtype.Numeric {
	return pgtype.Numeric{Int: big.NewInt(0), Valid: true}
}

// addNumeric adds exactly, keeping the finer of the two scales ("1.5" + "2.25" = "3.75").
func addNumeric(a, b pgtype.Numeric) pgtype.Numeric {
	if !b.Valid {
		return a
	}
	if !a.Valid {
		return b
	}
	exp := min(a.Exp, b.Exp)
	sum := new(big.Int).Add(scaled(a, exp), scaled(b, exp))
	return pgtype.Numeric{Int: sum, Exp: exp, Valid: true}
}

// scaled returns n's digits as an integer count of 10^exp, for exp <= n.Exp.
func scaled(n pgtype.Numeric, exp int32) *big.Int {
	factor := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(n.Exp-exp)), nil)
	return new(big.Int).Mul(n.Int, factor)
}

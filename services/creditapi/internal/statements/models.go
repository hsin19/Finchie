package statements

type Statement struct {
	ID      string
}

type Transaction struct {
	StatementID string
	ID          string
}

func (t *Transaction) Equals(other *Transaction) bool {
	return t.StatementID == other.StatementID && t.ID == other.ID
}

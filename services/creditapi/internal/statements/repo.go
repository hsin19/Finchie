package statements

type StatementRepository interface {
	GetStatement(id string) (*Statement, error)
	InsertStatement(statement *Statement) error
	UpdateStatement(statement *Statement) error
	GetTransactions(statementId string) ([]*Transaction, error)
	InsertTransaction(transactions *Transaction) error
	UpdateTransaction(transaction *Transaction) error
	DeleteTransaction(id string) error
}

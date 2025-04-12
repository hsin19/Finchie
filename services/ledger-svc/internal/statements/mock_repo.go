package statements

import (
	"errors"
	"sync"
)

type InMemoryRepo struct {
	statements   map[string]*Statement
	transactions map[string]Transaction
	mu           sync.RWMutex
}

func NewInMemoryRepo() *InMemoryRepo {
	return &InMemoryRepo{
		statements:   make(map[string]*Statement),
		transactions: make(map[string]Transaction),
	}
}

func (r *InMemoryRepo) GetStatement(id string) (*Statement, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	stmt, ok := r.statements[id]
	if !ok {
		return nil, nil
	}
	return stmt, nil
}

func (r *InMemoryRepo) UpsertStatement(statement *Statement) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.statements[statement.ID] = statement
	return nil
}

func (r *InMemoryRepo) GetTransactions(statementId string) ([]Transaction, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var result []Transaction
	for _, tx := range r.transactions {
		if tx.StatementID == statementId {
			result = append(result, tx)
		}
	}
	return result, nil
}

func (r *InMemoryRepo) UpsertTransaction(tx *Transaction) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.transactions[tx.ID] = *tx
	return nil
}

func (r *InMemoryRepo) DeleteTransaction(id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, ok := r.transactions[id]; !ok {
		return errors.New("transaction not found")
	}
	delete(r.transactions, id)
	return nil
}

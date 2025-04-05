package statements

// StatementService provides methods to interact with and manage statements.
type StatementService struct {
    Repo StatementRepository
}

// SaveStatement checks if the statement exists, then inserts or updates it based on comparison
func (s *StatementService) SaveStatement(statement *Statement) error {
    existing, err := s.Repo.GetStatement(statement.ID)
    if err != nil {
        return err
    }

    if existing == nil {
        return s.Repo.InsertStatement(statement)
    }
    
    if !existing.Equals(statement) {
        return s.Repo.UpdateStatement(statement)
    }
    
    return nil
}

// SyncTransactions synchronizes transactions between the provided list and existing ones in database
func (s *StatementService) SyncTransactions(statementID string, transactions []*Transaction) error {
    currentTransactions, err := s.Repo.GetTransactions(statementID)
    if err != nil {
        return err
    }

    newTxMap := make(map[string]*Transaction)
    for _, tx := range transactions {
        newTxMap[tx.ID] = tx
    }

    currentTxMap := make(map[string]*Transaction)
    for _, tx := range currentTransactions {
        currentTxMap[tx.ID] = tx
    }

    // Delete transactions that no longer exist
    for id := range currentTxMap {
        if _, exists := newTxMap[id]; !exists {
            err = s.Repo.DeleteTransaction(id)
            if err != nil {
                return err
            }
        }
    }

    // Update existing or insert new transactions
    for id, tx := range newTxMap {
        if currentTx, exists := currentTxMap[id]; exists {
            if !currentTx.Equals(tx) {
                err = s.Repo.UpdateTransaction(tx)
                if err != nil {
                    return err
                }
            }
        } else {
            err = s.Repo.InsertTransaction(tx)
            if err != nil {
                return err
            }
        }
    }

    return nil
}

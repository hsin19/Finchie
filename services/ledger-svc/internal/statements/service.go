package statements

type StatementService struct {
	Repo StatementRepository
}

func NewService(repo StatementRepository) *StatementService {
	return &StatementService{
		Repo: repo,
	}
}

func (s *StatementService) SaveStatement(statement *Statement) error {
	if err := statement.Normalize(); err != nil {
		return err
	}
	return s.Repo.UpsertStatement(statement)
}

func (s *StatementService) SyncTransactions(statementID string, transactions *[]Transaction) error {
	currentTransactions, err := s.Repo.GetTransactions(statementID)
	if err != nil {
		return err
	}

	newTxMap := make(map[string]*Transaction)
	for _, tx := range *transactions {
		if err := tx.Normalize(); err != nil {
			return err
		}
		err = s.Repo.UpsertTransaction(&tx)
		if err != nil {
			return err
		}
		newTxMap[tx.ID] = &tx
	}

	// Delete transactions that no longer exist
	for _, transaction := range currentTransactions {
		if _, exists := newTxMap[transaction.ID]; !exists {
			err = s.Repo.DeleteTransaction(transaction.ID)
			if err != nil {
				return err
			}
		}
	}

	return nil
}

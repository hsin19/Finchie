package statements

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
)

type StatementManager struct {
	Service *StatementService
	Repo    StatementRepository
}

type StatementDTO struct {
	ID           string
	Transactions []*TransactionDTO
}

type TransactionDTO struct {
	ID string
}

func (s *StatementManager) StatementsHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		s.getHandler(w, r)
	case http.MethodPost:
		s.postHandler(w, r)
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
}

func (s *StatementManager) getHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query()
	id := query.Get("id")
	if id == "" {
		http.Error(w, "Missing id parameter", http.StatusBadRequest)
		return
	}

	expandTx := shouldExpandTransactions(query)
	stmt, err := s.Repo.GetStatement(id)
	if err != nil {
		slog.Error("Failed to retrieve statement", "id", id, "error", err)
		http.Error(w, "Failed to retrieve statement", http.StatusInternalServerError)
		return
	}

	if stmt == nil {
		http.Error(w, "Statement not found", http.StatusNotFound)
		return
	}

	res := convertToStatementDTO(stmt)

	if expandTx {
		txs, err := s.Repo.GetTransactions(id)
		if err != nil {
			slog.Error("Failed to retrieve transactions for statement", "statement_id", id, "error", err)
			http.Error(w, "Failed to retrieve transactions", http.StatusInternalServerError)
			return
		}
		res.Transactions = make([]*TransactionDTO, len(txs))
		for i, tx := range txs {
			res.Transactions[i] = convertToTransactionDTO(tx)
		}
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(res); err != nil {
		slog.Error("Failed to encode JSON response", "error", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
}

func (s *StatementManager) postHandler(w http.ResponseWriter, r *http.Request) {
	var stmtDTO StatementDTO
	err := json.NewDecoder(r.Body).Decode(&stmtDTO)
	if err != nil {
		slog.Error("Failed to decode statement payload", "error", err)
		http.Error(w, "Invalid request payload", http.StatusBadRequest)
		return
	}

	stmt := convertToStatement(&stmtDTO)
	err = s.Service.SaveStatement(stmt)
	if err != nil {
		slog.Error("Failed to save statement", "id", stmt.ID, "error", err)
		http.Error(w, "Failed to save statement", http.StatusInternalServerError)
		return
	}

	expandTx := shouldExpandTransactions(r.URL.Query())
	if expandTx {
		tx := make([]*Transaction, len(stmtDTO.Transactions))
		for i, txDTO := range stmtDTO.Transactions {
			tx[i] = convertToTransaction(txDTO)
		}

		err = s.Service.SyncTransactions(stmt.ID, tx)
		if err != nil {
			slog.Error("Failed to sync transactions", "statement_id", stmt.ID, "tx_count", len(tx), "error", err)
			http.Error(w, "Failed to sync transactions", http.StatusInternalServerError)
			return
		}
	}

	w.Header().Set("Location", "/statements?id="+stmt.ID)
	w.WriteHeader(http.StatusCreated)
}

func shouldExpandTransactions(query url.Values) bool {
	expand := strings.SplitSeq(query.Get("$expand"), ",")
	for e := range expand {
		if strings.EqualFold(e, "transactions") {
			return true
		}
	}
	return false
}

func convertToStatement(statementDTO *StatementDTO) *Statement {
	return &Statement{
		ID: statementDTO.ID,
	}
}

func convertToStatementDTO(statement *Statement) *StatementDTO {
	return &StatementDTO{
		ID: statement.ID,
		// TODO: Add other fields as needed
	}
}

func convertToTransaction(transactionDTO *TransactionDTO) *Transaction {
	return &Transaction{
		ID: transactionDTO.ID,
	}
}

func convertToTransactionDTO(transaction *Transaction) *TransactionDTO {
	return &TransactionDTO{
		ID: transaction.ID,
		// TODO: Add other fields as needed
	}
}

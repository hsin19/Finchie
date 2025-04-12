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

	expandTx := shouldExpandTransactions(query)
	if expandTx {
		txs, err := s.Repo.GetTransactions(id)
		if err != nil {
			slog.Error("Failed to retrieve transactions for statement", "statement_id", id, "error", err)
			http.Error(w, "Failed to retrieve transactions", http.StatusInternalServerError)
			return
		}
		stmt.Transactions = &txs
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(stmt); err != nil {
		slog.Error("Failed to encode JSON response", "error", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
}

func (s *StatementManager) postHandler(w http.ResponseWriter, r *http.Request) {
	var stmt Statement
	err := json.NewDecoder(r.Body).Decode(&stmt)
	if err != nil {
		slog.Error("Failed to decode statement payload", "error", err)
		http.Error(w, "Invalid request payload", http.StatusBadRequest)
		return
	}

	err = s.Service.SaveStatement(&stmt)
	if err != nil {
		slog.Error("Failed to update statement", "id", stmt.ID, "error", err)
		http.Error(w, "Failed to update statement", http.StatusInternalServerError)
		return
	}

	expandTx := shouldExpandTransactions(r.URL.Query())
	if expandTx {
		if stmt.Transactions == nil {
			http.Error(w, "Transactions null when expanding", http.StatusBadRequest)
			return
		}

		err = s.Service.SyncTransactions(stmt.ID, stmt.Transactions)
		if err != nil {
			slog.Error("Failed to sync transactions", "statement_id", stmt.ID, "tx_count", len(*stmt.Transactions), "error", err)
			http.Error(w, "Failed to sync transactions", http.StatusInternalServerError)
			return
		}
	}

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

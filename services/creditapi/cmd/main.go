package main

import (
	"log"
	"net/http"

	"github.com/hsin19/Finchie/services/creditapi/internal/statements"
)

func main() {
	statementsManager := statements.StatementManager{
		// TODO: Initialize the service and repository here
	}

	http.HandleFunc("/api/statements", statementsManager.StatementsHandler)
    log.Fatal(http.ListenAndServe(":8080", nil))
}

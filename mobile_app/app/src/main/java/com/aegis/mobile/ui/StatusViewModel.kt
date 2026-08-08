package com.aegis.mobile.ui

import androidx.lifecycle.LiveData
import androidx.lifecycle.Transformations
import androidx.lifecycle.ViewModel
import com.aegis.mobile.data.SignalRepository
import com.aegis.mobile.models.AnalysisResponse

class StatusViewModel : ViewModel() {

    // Raw latest result from the "brain" server
    val currentResult: LiveData<AnalysisResponse> = SignalRepository.latestResult

    // Convenience streams derived from currentResult, used directly by MainActivity
    val signal: LiveData<String> = Transformations.map(currentResult) { it.signal }
    val details: LiveData<String> = Transformations.map(currentResult) { it.details }
    val confidence: LiveData<Float> = Transformations.map(currentResult) { it.confidence }
}
